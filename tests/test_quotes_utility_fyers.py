# -*- coding: utf-8 -*-
"""QuoteUtility integration tests using a fake Fyers data socket."""

import unittest

import pandas as pd

from DataTypes.trade_data import quote_data
from Utility.quotes_utility import QuoteUtility


def epoch_ist(hour, minute):
    return int(pd.Timestamp(f"2026-10-27 {hour:02d}:{minute:02d}:00",
                            tz="Asia/Kolkata").timestamp())


class FakeDataWebsocket:
    def __init__(self):
        self.subscribed = []
        self.unsubscribed = []
        self.closed = False
        self.ticks = pd.DataFrame([
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 15),
             "ltp": 100.5, "vol_traded_today": 10,
             "bid_price": 100.4, "ask_price": 100.6},
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 16),
             "ltp": 101.0, "vol_traded_today": 12,
             "bid_price": 100.9, "ask_price": 101.1},
        ])

    def subscribe(self, p_lst_symbols):
        self.subscribed.extend(p_lst_symbols)

    def unsubscribe(self, p_lst_symbols):
        self.unsubscribed.extend(p_lst_symbols)

    def get_tick_data(self):
        return self.ticks.copy()

    def close(self):
        self.closed = True


class FakeBrokerUtility:
    def __init__(self):
        self.data_websocket = FakeDataWebsocket()
        self.quote_calls = []
        self.fetch_ohlc_calls = []
        self.option_chain_calls = []
        self.candle_data = pd.DataFrame([{"close": 101.0}])
        self.option_chain_data = pd.DataFrame([{"symbol": "NSE:SBINCE", "ltp": 10.0}])

    def get_quotes(self, p_lst_quote_requests):
        self.quote_calls.append(list(p_lst_quote_requests))
        return {request.symbol: quote_data(p_ltp=99.0)
                for request in p_lst_quote_requests}

    def fetchOHLC(self, **kwargs):
        self.fetch_ohlc_calls.append(kwargs)
        return self.candle_data

    def getOptionChain(self, underlying):
        self.option_chain_calls.append(underlying)
        return self.option_chain_data, 0, 0

    def get_data_websocket(self):
        return self.data_websocket

    @staticmethod
    def get_data_websocket_symbol(p_symbol, p_market_type):
        if p_market_type and p_market_type != "FUT":
            return f"NSE:{p_symbol}-{p_market_type}"
        return f"NSE:{p_symbol}"


class FakeTradeUtility:
    def __init__(self, broker_utility):
        self.broker_utility = broker_utility

    def get_broker_utility(self):
        return self.broker_utility


class QuoteUtilityFyersTests(unittest.TestCase):
    def setUp(self):
        self.broker = FakeBrokerUtility()
        self.quotes = QuoteUtility(p_interval=0.05)
        self.quotes.set_trade_utility(FakeTradeUtility(self.broker))
        self.addCleanup(self._stop_quotes)

    def _stop_quotes(self):
        self.quotes.stop()
        self.quotes.get_thread_info().join(timeout=1)

    def test_rest_quote_shape_is_preserved_and_tick_candle_accessors_are_added(self):
        self.quotes.add_stocks(["SBIN"], ["EQ"])

        quote = self.quotes.get_quote_data()["SBIN"]
        self.assertIsInstance(quote, quote_data)
        self.assertEqual(quote.ltp, 99.0)
        self.assertEqual(self.broker.data_websocket.subscribed, ["NSE:SBIN-EQ"])
        self.assertEqual(len(self.quotes.get_tick_data()), 2)

        candles = self.quotes.get_5min_candle_data()
        self.assertEqual(list(candles), ["SBIN"])
        self.assertEqual(candles["SBIN"]["open"].tolist(), [100.5])
        self.assertEqual(candles["SBIN"]["close"].tolist(), [101.0])
        self.assertEqual(candles["SBIN"]["volume"].tolist(), [2])

    def test_quote_data_can_come_from_websocket_ticks(self):
        self.quotes.quote_source = "websocket"
        self.quotes.add_stocks(["SBIN"], ["EQ"])

        quote = self.quotes.get_quote_data()["SBIN"]
        self.assertIsInstance(quote, quote_data)
        self.assertEqual(quote.ltp, 101.0)
        self.assertEqual(quote.ask, 100.9)
        self.assertEqual(quote.volume, 12.0)
        self.assertEqual(self.broker.quote_calls, [])

    def test_add_stocks_seeds_initial_chain_prices(self):
        self.quotes.add_stocks(["SBIN"], ["EQ"], p_initial_prices={"SBIN": 104.5})

        self.assertEqual(self.quotes.get_quote_data()["SBIN"].ltp, 104.5)

    def test_option_chain_snapshot_is_cached_for_shared_strategy_engines(self):
        first_chain, _, _ = self.quotes.get_option_chain_snapshot("NIFTY50-INDEX")
        second_chain, _, _ = self.quotes.get_option_chain_snapshot("NIFTY50-INDEX")

        self.assertEqual(self.broker.option_chain_calls, ["NIFTY50-INDEX"])
        self.assertIsNot(first_chain, second_chain)
        self.assertEqual(first_chain.iloc[0]["ltp"], 10.0)

    def test_remove_unsubscribes_and_symbol_can_be_added_again(self):
        self.quotes.add_stocks(["SBIN"], ["EQ"])
        self.quotes.remove_stock("SBIN")
        self.quotes.add_stocks(["SBIN"], ["EQ"])

        self.assertEqual(self.broker.data_websocket.unsubscribed, ["NSE:SBIN-EQ"])
        self.assertEqual(self.broker.data_websocket.subscribed,
                         ["NSE:SBIN-EQ", "NSE:SBIN-EQ"])
        self.assertEqual(len(self.broker.quote_calls[-1]), 1)

    def test_stop_closes_the_optional_socket(self):
        self.quotes.add_stocks(["SBIN"], ["EQ"])
        self.quotes.stop()

        self.assertTrue(self.broker.data_websocket.closed)

    def test_fetch_ohlc_builds_candles_from_websocket_ticks(self):
        candles = self.quotes.fetchOHLC(
            "SBIN", "2026-10-27 09:15:00", "2026-10-27 09:20:00", "5minute")

        self.assertEqual(candles["open"].tolist(), [100.5])
        self.assertEqual(candles["close"].tolist(), [101.0])
        self.assertEqual(self.broker.data_websocket.subscribed, ["NSE:SBIN-EQ"])
        self.assertEqual(self.broker.fetch_ohlc_calls, [])

    def test_fetch_ohlc_can_use_broker_source(self):
        self.quotes.candle_source = "broker"

        candles = self.quotes.fetchOHLC(
            "SBIN", "2026-10-27 09:15:00", "2026-10-27 15:30:00", "15minute")

        self.assertIs(candles, self.broker.candle_data)
        self.assertEqual(self.broker.fetch_ohlc_calls, [{
            "ticker": "SBIN",
            "str_from_date": "2026-10-27 09:15:00",
            "str_to_date": "2026-10-27 15:30:00",
            "interval": "15minute",
            "all_data": False,
            "exchange": "NSE",
            "market_type": "EQ",
        }])

    def test_fetch_ohlc_can_override_configured_source(self):
        candles = self.quotes.fetchOHLC(
            "SBIN", "2026-10-27 09:15:00", "2026-10-27 15:30:00", "15minute",
            source="broker")

        self.assertIs(candles, self.broker.candle_data)


if __name__ == "__main__":
    unittest.main()
