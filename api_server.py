import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import yfinance as yf
from dotenv import load_dotenv

# โหลดตัวแปรจาก .env และตั้งค่า path
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# นำเข้า Notifier ที่ทำไว้
from utils.notifier import Notifier
import market_scanner

PORT = 5000
CONFIG_PATH = "config.json"
PORTFOLIO_PATH = "portfolio.json"

# กำหนดตัวแจ้งเตือน
notifier = Notifier()

class PortfolioAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self.path = '/dashboard.html'
            return super().do_GET()
            
        if self.path.startswith('/api/portfolio'):
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    portfolio = json.load(f)
                
                response_data = json.dumps(portfolio).encode()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path.startswith('/api/scan?'):
            parsed_path = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed_path.query)
            market = query.get("market", ["TH"])[0]
            
            try:
                results = market_scanner.run_scan(market)
                response_data = json.dumps(results).encode()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
            except Exception as e:
                self.send_error_response(500, str(e))
        elif self.path == '/api/scan-portfolio':
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    portfolio = json.load(f)
                
                symbols = [item["symbol"] for item in portfolio]
                results = market_scanner.scan_symbols(symbols)
                
                # Auto update tags in portfolio.json based on scan results
                for item in portfolio:
                    for res in results:
                        if res["symbol"] == item["symbol"]:
                            # Ignore error tags if it fails to fetch momentarily
                            if "❌" not in res["tags"][0]:
                                item["tags"] = res["tags"]
                                # Sync name if it exists
                                if "name" in res:
                                    item["name"] = res["name"]
                            break
                            
                with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                    json.dump(portfolio, f, indent=4, ensure_ascii=False)
                
                response_data = json.dumps(results).encode()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
            except Exception as e:
                self.send_error_response(500, str(e))
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path == '/api/portfolio':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            symbol = data.get("symbol", "").upper()
            
            if not symbol:
                self.send_error_response(400, "Symbol is required")
                return

            # สำหรับตลาดหุ้นไทย / Settrade เรามักจะต้องใช้ .BK
            # หากผู้ใช้ไม่ได้ใส่ . และไม่ใช่ดัชนีพิเศษ ให้เติม .BK อัตโนมัติ
            if "." not in symbol and not symbol.startswith("^"):
                symbol += ".BK"

            # Validate symbol using yfinance
            try:
                print(f"Validating {symbol}...")
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
                if hist.empty:
                    self.send_error_response(400, f"Cannot find symbol: {symbol}")
                    return
            except Exception as e:
                self.send_error_response(400, f"Validation failed: {str(e)}")
                return
                
            # Add to config
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    portfolio = json.load(f)
                
                # Check if exists
                for item in portfolio:
                    if item["symbol"] == symbol:
                        self.send_error_response(400, f"Symbol {symbol} already exists in portfolio")
                        return
                        
                full_name = ticker.info.get('longName') or ticker.info.get('shortName') or symbol
                portfolio.append({
                    "symbol": symbol,
                    "name": full_name,
                    "allocation_check": 0.1,
                    "enabled": True,
                    "tags": data.get("tags", ["✋ Manual"])
                })
                
                with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                    json.dump(portfolio, f, indent=4, ensure_ascii=False)
                    
                # แจ้งเตือนเมื่อมีการเพิ่มสำเร็จ
                notifier.send(f"🟢 [System] มีการเพิ่มรายชื่อหุ้น {symbol} เข้าสู่พอร์ตระบบเทรดเรียบร้อยแล้ว!")
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
                
            except Exception as e:
                self.send_error_response(500, str(e))
                
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/api/portfolio/toggle':
            query = urllib.parse.parse_qs(parsed_path.query)
            symbol = query.get("symbol", [""])[0]
            
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    portfolio = json.load(f)
                    
                found = False
                is_enabled_now = False
                for item in portfolio:
                    if item["symbol"] == symbol:
                        # Toggle logic
                        item["enabled"] = not item.get("enabled", True)
                        is_enabled_now = item["enabled"]
                        found = True
                        break
                        
                if not found:
                    self.send_error_response(404, "Symbol not found")
                    return
                    
                with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                    json.dump(portfolio, f, indent=4, ensure_ascii=False)
                    
                # แจ้งเตือนเมื่อสลับโหมด
                status_text = "เปิดใช้งานพอร์ต (Enabled)" if is_enabled_now else "ระงับการเทรดชั่วคราว (Disabled)"
                emoji = "✅" if is_enabled_now else "🟡"
                notifier.send(f"{emoji} [System] อัปเดตสถานะหุ้น {symbol} -> {status_text} แล้ว")
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_error_response(500, str(e))

    def do_DELETE(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/api/portfolio':
            query = urllib.parse.parse_qs(parsed_path.query)
            symbol = query.get("symbol", [""])[0]
            
            if not symbol:
                self.send_error_response(400, "Symbol is required")
                return
                
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    portfolio = json.load(f)
                    
                initial_len = len(portfolio)
                # Keep items that are NOT the symbol
                portfolio = [item for item in portfolio if item["symbol"] != symbol]
                
                if len(portfolio) == initial_len:
                    self.send_error_response(404, "Symbol not found")
                    return
                    
                with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                    json.dump(portfolio, f, indent=4, ensure_ascii=False)
                    
                # แจ้งเตือนมื่อลบทิ้ง
                notifier.send(f"🔴 [System] หุ้น {symbol} ถูกถอดออกจากพอร์ตระบบการเทรดแล้ว")
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
                
            except Exception as e:
                self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), PortfolioAPIHandler) as httpd:
        print(f"Starting UI Web Server at http://localhost:{PORT}")
        httpd.serve_forever()
