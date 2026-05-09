import urllib.request
import re
from html.parser import HTMLParser

class WikiTableParser(HTMLParser):
    def __init__(self, target_table_index=1):
        super().__init__()
        self.in_table = False
        self.in_tbody = False
        self.in_tr = False
        self.td_count = 0
        self.in_symbol_td = False
        self.symbols = []
        self.table_count = 0
        self.target_table_index = target_table_index

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            attr_dict = dict(attrs)
            if 'wikitable' in attr_dict.get('class', ''):
                self.table_count += 1
                if self.table_count == self.target_table_index:
                    self.in_table = True
        elif self.in_table and tag == 'tbody':
            self.in_tbody = True
        elif self.in_table and tag == 'tr':
            self.in_tr = True
            self.td_count = 0
        elif self.in_tr and tag == 'td':
            self.td_count += 1
            # Usually symbol is in the first column for S&P500 and second column for SET50 (Wait, let's just grab all uppercase words in all tds and validate)
            self.in_symbol_td = True

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_table:
            self.in_table = False
        elif tag == 'tr':
            self.in_tr = False
        elif tag == 'td':
            self.in_symbol_td = False

    def handle_data(self, data):
        if self.in_symbol_td and data.strip():
            symbol = data.strip()
            # Valid symbol like AAPL or PTT (no spaces, all caps, 1-10 chars)
            if re.match(r'^[A-Z0-9\-]{1,10}$', symbol):
                self.symbols.append(symbol)

def get_set50_symbols():
    try:
        req = urllib.request.Request("https://en.wikipedia.org/wiki/SET50_Index_and_SET100_Index", headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        parser = WikiTableParser(target_table_index=1)
        parser.feed(html)
        # Filter symbols that look like Thai tickers and add .BK
        # Wikipedia table has both names and symbols. We can filter by those that are uppercase
        symbols = [s + ".BK" for s in parser.symbols if s.isupper()]
        # Remove duplicates preserving order
        unique_symbols = list(dict.fromkeys(symbols))
        return unique_symbols[:50] # Just take top 50
    except Exception as e:
        print(f"Error fetching SET50: {e}")
        return []

def get_sp500_symbols():
    try:
        req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        parser = WikiTableParser(target_table_index=1)
        parser.feed(html)
        symbols = [s for s in parser.symbols if s.isupper()]
        unique_symbols = list(dict.fromkeys(symbols))
        return unique_symbols[:500]
    except Exception as e:
        print(f"Error fetching SP500: {e}")
        return []

