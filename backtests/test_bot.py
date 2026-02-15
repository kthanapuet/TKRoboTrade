"""
Unit Tests for TK Robo Trade Bot
Tests all major functions and scenarios in bot.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, time as datetime_time
import sys
import os
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import bot functions
from bot import is_market_open, run_bot, send_daily_summary


class TestMarketHours(unittest.TestCase):
    """Test market open/close detection"""
    
    @patch('bot.datetime')
    def test_market_open_morning(self, mock_datetime):
        """Test market is open during morning session (10:00-12:30)"""
        mock_now = Mock()
        mock_now.weekday.return_value = 2  # Wednesday
        mock_now.time.return_value = datetime_time(11, 0)
        mock_datetime.now.return_value = mock_now
        
        self.assertTrue(is_market_open())
    
    @patch('bot.datetime')
    def test_market_open_afternoon(self, mock_datetime):
        """Test market is open during afternoon session (14:30-16:30)"""
        mock_now = Mock()
        mock_now.weekday.return_value = 3  # Thursday
        mock_now.time.return_value = datetime_time(15, 0)
        mock_datetime.now.return_value = mock_now
        
        self.assertTrue(is_market_open())
    
    @patch('bot.datetime')
    def test_market_closed_weekend(self, mock_datetime):
        """Test market is closed on weekends"""
        mock_now = Mock()
        mock_now.weekday.return_value = 5  # Saturday
        mock_now.time.return_value = datetime_time(11, 0)
        mock_datetime.now.return_value = mock_now
        
        self.assertFalse(is_market_open())
    
    @patch('bot.datetime')
    def test_market_closed_lunch(self, mock_datetime):
        """Test market is closed during lunch (12:30-14:30)"""
        mock_now = Mock()
        mock_now.weekday.return_value = 1  # Tuesday
        mock_now.time.return_value = datetime_time(13, 0)
        mock_datetime.now.return_value = mock_now
        
        self.assertFalse(is_market_open())
    
    @patch('bot.datetime')
    def test_market_closed_after_hours(self, mock_datetime):
        """Test market is closed after 16:30"""
        mock_now = Mock()
        mock_now.weekday.return_value = 4  # Friday
        mock_now.time.return_value = datetime_time(17, 0)
        mock_datetime.now.return_value = mock_now
        
        self.assertFalse(is_market_open())


class TestBuyScenarios(unittest.TestCase):
    """Test BUY order scenarios"""
    
    def setUp(self):
        """Set up mocks for each test"""
        self.mock_investor = Mock()
        self.mock_market = Mock()
        self.mock_equity = Mock()
        
        self.mock_investor.MarketData.return_value = self.mock_market
        self.mock_investor.Equity.return_value = self.mock_equity
        
        self.mock_notifier = Mock()
        self.mock_strategy = Mock()
        self.strategies_map = {'NVDA80.BK': self.mock_strategy}
        
        self.portfolio_config = [{
            'symbol': 'NVDA80.BK',
            'allocation_check': 0.1
        }]
        
        self.trade_tracker = {}
    
    @patch('bot.datetime')
    def test_buy_signal_success(self, mock_datetime):
        """Test successful BUY order when position is 0"""
        # Mock datetime
        mock_now = datetime(2026, 2, 15, 10, 30)
        mock_datetime.now.return_value = mock_now
        
        # Mock portfolio (no position)
        self.mock_equity.get_portfolios.return_value = {
            'portfolio_list': [],
            'total_portfolio_market_value': 0
        }
        
        # Mock account info
        self.mock_equity.get_account_info.return_value = {
            'line_available': 50000,
            'cash_balance': 50000
        }
        
        # Mock candlestick data
        candle_data = [
            {'time': 1708000000, 'open': 120, 'high': 125, 'low': 119, 'close': 124}
        ] * 200
        self.mock_market.get_candlestick.return_value = candle_data
        
        # Mock strategy signal (BUY)
        mock_df = pd.DataFrame({
            'close': [124],
            'Position': [2],  # BUY signal
            'Status_Text': ['SMA Crossover (Fast > Slow)']
        }, index=[0])
        self.mock_strategy.generate_signals.return_value =mock_df
        self.mock_strategy.__class__.__name__ = 'SMACrossover'
        
        # Mock order response
        self.mock_equity.place_order.return_value = {'order_no': 'ORD123'}
        
        # Run bot
        run_bot(
            self.mock_investor,
            'ACC001',
            '1234',
            self.strategies_map,
            self.mock_notifier,
            self.portfolio_config,
            self.trade_tracker
        )
        
        # Verify order was placed
        self.mock_equity.place_order.assert_called_once()
        call_args = self.mock_equity.place_order.call_args
        self.assertEqual(call_args[1]['side'], 'Buy')
        self.assertEqual(call_args[1]['symbol'], 'NVDA80')
        
        # Verify trade tracker updated
        self.assertIn('NVDA80', self.trade_tracker)
        self.assertEqual(self.trade_tracker['NVDA80']['entry_price'], 124)
        
        # Verify notifications sent
        self.assertEqual(self.mock_notifier.send.call_count, 2)  # Buy msg + Order confirm
    
    def test_buy_signal_already_holding(self):
        """Test BUY signal when already holding position (should skip)"""
        # Mock portfolio (already holding)
        self.mock_equity.get_portfolios.return_value = {
            'portfolio_list': [{
                'symbol': 'NVDA80',
                'actual_volume': 100,
                'average_price': 120
            }],
            'total_portfolio_market_value': 12000
        }
        
        self.mock_equity.get_account_info.return_value = {
            'line_available': 50000,
            'cash_balance': 50000
        }
        
        candle_data = [
            {'time': 1708000000, 'open': 120, 'high': 125, 'low': 119, 'close': 124}
        ] * 200
        self.mock_market.get_candlestick.return_value = candle_data
        
        # BUY signal but already holding
        mock_df = pd.DataFrame({
            'close': [124],
            'Position': [2],
            'Status_Text': ['SMA Crossover']
        }, index=[0])
        self.mock_strategy.generate_signals.return_value = mock_df
        self.mock_strategy.__class__.__name__ = 'SMACrossover'
        
        run_bot(
            self.mock_investor,
            'ACC001',
            '1234',
            self.strategies_map,
            self.mock_notifier,
            self.portfolio_config,
            self.trade_tracker
        )
        
        # Verify NO order placed
        self.mock_equity.place_order.assert_not_called()


class TestSellScenarios(unittest.TestCase):
    """Test SELL order scenarios"""
    
    def setUp(self):
        self.mock_investor = Mock()
        self.mock_market = Mock()
        self.mock_equity = Mock()
        
        self.mock_investor.MarketData.return_value = self.mock_market
        self.mock_investor.Equity.return_value = self.mock_equity
        
        self.mock_notifier = Mock()
        self.mock_strategy = Mock()
        self.strategies_map = {'TSLA80.BK': self.mock_strategy}
        
        self.portfolio_config = [{
            'symbol': 'TSLA80.BK',
            'allocation_check': 0.1
        }]
    
    @patch('bot.datetime')
    def test_sell_signal_profit(self, mock_datetime):
        """Test SELL order with profit"""
        # Mock datetime
        entry_time = datetime(2026, 2, 1, 10, 0)
        exit_time = datetime(2026, 2, 15, 15, 0)
        mock_datetime.now.return_value = exit_time
        
        # Trade tracker with entry info
        trade_tracker = {
            'TSLA80': {
                'entry_date': entry_time,
                'entry_price': 200.0,
                'entry_vol': 50
            }
        }
        
        # Mock portfolio (holding position)
        self.mock_equity.get_portfolios.return_value = {
            'portfolio_list': [{
                'symbol': 'TSLA80',
                'actual_volume': 50,
                'average_price': 200
            }],
            'total_portfolio_market_value': 11000
        }
        
        self.mock_equity.get_account_info.return_value = {
            'line_available': 10000,
            'cash_balance': 10000
        }
        
        candle_data = [
            {'time': 1708000000, 'open': 220, 'high': 225, 'low': 218, 'close': 220}
        ] * 200
        self.mock_market.get_candlestick.return_value = candle_data
        
        # SELL signal
        mock_df = pd.DataFrame({
            'close': [220],
            'Position': [-2],  # SELL signal
            'Status_Text': ['SMA Crossunder']
        }, index=[0])
        self.mock_strategy.generate_signals.return_value = mock_df
        self.mock_strategy.__class__.__name__ = 'SMACrossover'
        
        self.mock_equity.place_order.return_value = {'order_no': 'ORD456'}
        
        run_bot(
            self.mock_investor,
            'ACC001',
            '1234',
            self.strategies_map,
            self.mock_notifier,
            self.portfolio_config,
            trade_tracker
        )
        
        # Verify SELL order placed
        self.mock_equity.place_order.assert_called_once()
        call_args = self.mock_equity.place_order.call_args
        self.assertEqual(call_args[1]['side'], 'Sell')
        self.assertEqual(call_args[1]['volume'], 50)
        
        # Verify trade tracker cleared
        self.assertNotIn('TSLA80', trade_tracker)
        
        # Verify notification contains P&L
        notification_calls = [str(call) for call in self.mock_notifier.send.call_args_list]
        self.assertTrue(any('💚 SELL ORDER' in str(call) for call in notification_calls))
        self.assertTrue(any('+1,000.00' in str(call) for call in notification_calls))  # Profit
        self.assertTrue(any('+10.00%' in str(call) for call in notification_calls))
    
    @patch('bot.datetime')
    def test_sell_signal_loss(self, mock_datetime):
        """Test SELL order with loss (Stop Loss)"""
        entry_time = datetime(2026, 2, 10, 14, 0)
        exit_time = datetime(2026, 2, 15, 10, 0)
        mock_datetime.now.return_value = exit_time
        
        trade_tracker = {
            'TSLA80': {
                'entry_date': entry_time,
                'entry_price': 200.0,
                'entry_vol': 50
            }
        }
        
        self.mock_equity.get_portfolios.return_value = {
            'portfolio_list': [{
                'symbol': 'TSLA80',
                'actual_volume': 50,
                'average_price': 200
            }],
            'total_portfolio_market_value': 9500
        }
        
        self.mock_equity.get_account_info.return_value = {
            'line_available': 10000,
            'cash_balance': 10000
        }
        
        candle_data = [
            {'time': 1708000000, 'open': 190, 'high': 192, 'low': 189, 'close': 190}
        ] * 200
        self.mock_market.get_candlestick.return_value = candle_data
        
        # SELL signal with Stop Loss
        mock_df = pd.DataFrame({
            'close': [190],
            'Position': [-2],
            'Status_Text': ['Stop Loss (-5%)']
        }, index=[0])
        self.mock_strategy.generate_signals.return_value = mock_df
        self.mock_strategy.__class__.__name__ = 'SMACrossover'
        
        self.mock_equity.place_order.return_value = {'order_no': 'ORD789'}
        
        run_bot(
            self.mock_investor,
            'ACC001',
            '1234',
            self.strategies_map,
            self.mock_notifier,
            self.portfolio_config,
            trade_tracker
        )
        
        # Verify notification contains loss
        notification_calls = [str(call) for call in self.mock_notifier.send.call_args_list]
        self.assertTrue(any('🔴 SELL ORDER' in str(call) for call in notification_calls))
        self.assertTrue(any('-500.00' in str(call) for call in notification_calls))  # Loss
        self.assertTrue(any('Stop Loss' in str(call) for call in notification_calls))


class TestDailySummary(unittest.TestCase):
    """Test daily summary function"""
    
    def setUp(self):
        self.mock_investor = Mock()
        self.mock_equity = Mock()
        self.mock_investor.Equity.return_value = self.mock_equity
        self.mock_notifier = Mock()
    
    def test_daily_summary_with_orders(self):
        """Test daily summary with matched orders"""
        self.mock_equity.get_portfolios.return_value = {
            'total_portfolio_market_value': 100000,
            'portfolio_list': []
        }
        
        self.mock_equity.get_account_info.return_value = {
            'cash_balance': 50000
        }
        
        self.mock_equity.get_orders.return_value = [
            {
                'symbol': 'NVDA80',
                'side': 'Buy',
                'vol': 100,
                'price': 125.50,
                'show_order_status': 'Matched'
            },
            {
                'symbol': 'TSLA80',
                'side': 'Sell',
                'vol': 50,
                'price': 220.00,
                'show_order_status': 'Matched'
            }
        ]
        
        send_daily_summary(self.mock_investor, 'ACC001', self.mock_notifier)
        
        # Verify summary sent
        self.mock_notifier.send.assert_called_once()
        summary = str(self.mock_notifier.send.call_args)
        
        # Check summary contains key info
        self.assertIn('150,000', summary)  # Total equity
        self.assertIn('Matched: 2', summary)
        self.assertIn('NVDA80', summary)
        self.assertIn('TSLA80', summary)
    
    def test_daily_summary_no_orders(self):
        """Test daily summary with no orders"""
        self.mock_equity.get_portfolios.return_value = {
            'total_portfolio_market_value': 80000,
            'portfolio_list': []
        }
        
        self.mock_equity.get_account_info.return_value = {
            'cash_balance': 20000
        }
        
        self.mock_equity.get_orders.return_value = []
        
        send_daily_summary(self.mock_investor, 'ACC001', self.mock_notifier)
        
        self.mock_notifier.send.assert_called_once()
        summary = str(self.mock_notifier.send.call_args)
        self.assertIn('No orders today', summary)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        self.mock_investor = Mock()
        self.mock_market = Mock()
        self.mock_equity = Mock()
        
        self.mock_investor.MarketData.return_value = self.mock_market
        self.mock_investor.Equity.return_value = self.mock_equity
        
        self.mock_notifier = Mock()
        self.mock_strategy = Mock()
        self.strategies_map = {'AAPL80.BK': self.mock_strategy}
        
        self.portfolio_config = [{
            'symbol': 'AAPL80.BK',
            'allocation_check': 0.1
        }]
        
        self.trade_tracker = {}
    
    def test_api_error_handling(self):
        """Test handling of API errors"""
        # Simulate API error
        self.mock_equity.get_portfolios.side_effect = Exception("API Timeout")
        
        # Should not crash
        try:
            run_bot(
                self.mock_investor,
                'ACC001',
                '1234',
                self.strategies_map,
                self.mock_notifier,
                self.portfolio_config,
                self.trade_tracker
            )
        except Exception as e:
            self.fail(f"run_bot raised exception when it shouldn't: {e}")
        
        # Should send error notification
        error_calls = [str(call) for call in self.mock_notifier.send.call_args_list]
        self.assertTrue(any('❌' in str(call) for call in error_calls))
    
    def test_missing_candlestick_data(self):
        """Test handling of missing candlestick data"""
        self.mock_equity.get_portfolios.return_value = {
            'portfolio_list': [],
            'total_portfolio_market_value': 0
        }
        
        self.mock_equity.get_account_info.return_value = {
            'line_available': 50000,
            'cash_balance': 50000
        }
        
        # Simulate candlestick error
        self.mock_market.get_candlestick.side_effect = Exception("Symbol not found")
        
        # Should not crash
        run_bot(
            self.mock_investor,
            'ACC001',
            '1234',
            self.strategies_map,
            self.mock_notifier,
            self.portfolio_config,
            self.trade_tracker
        )
        
        # Should continue to next stock (no order placed)
        self.mock_equity.place_order.assert_not_called()


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMarketHours))
    suite.addTests(loader.loadTestsFromTestCase(TestBuyScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestSellScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestDailySummary))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"✅ Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Failed: {len(result.failures)}")
    print(f"⚠️ Errors: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
