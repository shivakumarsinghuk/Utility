# -*- coding: utf-8 -*-


import threading
from BrokerUtility.pal.utility_manager import *
import pandas as pd
from DataTypes.defines import DATE_TIME
from DataTypes.trade_data import quote_data

from .fyers_candle_utility import FyersCandleUtility

class QuoteUtility:
    """Poll REST quotes and optionally expose live FYERS ticks and candles."""

    def __init__(self, p_interval=2, candle_source="broker", quote_source="broker"):
        self.trade_utility = None
        self.candle_source = self._normalize_candle_source(candle_source)
        self.quote_source = self._normalize_quote_source(quote_source)
        self.lst_stocks = []
        self.lst_get_quote_req = []
        self._stocks_lock = threading.RLock()
        self._option_chain_lock = threading.Lock()
        self._option_chain_cache = {}
        self.interval = p_interval
        self.execute_thread = threading.Thread(target=self.execute)
        self.dict_quote_data = {}
        self._ltp_high_watermarks = {}
        self._quote_lock = threading.Lock()
        self.is_stopped = False
        self.stop_event = threading.Event()
        # The WebSocket is optional and discovered from broker methods at
        # runtime, so brokers without the FYERS stream keep their existing path.
        self.data_websocket = None
        self.fyers_candle_utility = FyersCandleUtility()

        # start the thread
        self.execute_thread.start()


    def set_trade_utility(self, p_trade_utility):
        if self.trade_utility is None:
            self.trade_utility = p_trade_utility

    def get_thread_info(self):
        return self.execute_thread

    def execute(self):
        self.stop_event.wait(self.interval)
        while not self.stop_event.is_set():
            #check whether stocks list having atleast one stock
            if len(self.lst_stocks) > 0:
                if self.stop_event.wait(4):
                    break
                if self.trade_utility:
                    self._refresh_quote_data()
        print("Getquote Stopped")

    def _get_data_websocket(self):
        """Lazily acquire a broker's optional stream using the existing interface."""
        if self.data_websocket is not None or self.trade_utility is None:
            return self.data_websocket

        broker_utility = self.trade_utility.get_broker_utility()
        get_data_websocket = getattr(broker_utility, "get_data_websocket", None)
        if callable(get_data_websocket):
            self.data_websocket = get_data_websocket()
        return self.data_websocket

    def _get_websocket_symbol(self, p_quote_req_data):
        """Ask the broker to format a quote request as its feed symbol."""
        if self.trade_utility is None:
            return None
        broker_utility = self.trade_utility.get_broker_utility()
        get_data_websocket_symbol = getattr(broker_utility, "get_data_websocket_symbol", None)
        if not callable(get_data_websocket_symbol):
            return None
        return get_data_websocket_symbol(p_quote_req_data.symbol,
                                         p_quote_req_data.market_type)

    def add_stocks(self, p_lst_stocks, p_lst_market_type, p_initial_prices=None):
        with self._stocks_lock:
            self._add_stocks(p_lst_stocks, p_lst_market_type, p_initial_prices)

    def _add_stocks(self, p_lst_stocks, p_lst_market_type, p_initial_prices=None):
        lst_new_quote_requests = []
        p_initial_prices = p_initial_prices or {}
        for index, stock in enumerate(p_lst_stocks):
            if stock not in self.lst_stocks:
                self.lst_stocks.append(stock)
                obj_get_quotes_req_data = get_quote_request_data(p_symbol=stock, p_market_type=p_lst_market_type[index])
                self.lst_get_quote_req.append(obj_get_quotes_req_data)
                lst_new_quote_requests.append(obj_get_quotes_req_data)
        if lst_new_quote_requests:
            data_websocket = self._get_data_websocket()
            if data_websocket is not None:
                lst_symbols = [self._get_websocket_symbol(quote_req)
                               for quote_req in lst_new_quote_requests]
                lst_symbols = [symbol for symbol in lst_symbols if symbol]
                if lst_symbols:
                    data_websocket.subscribe(lst_symbols)
        self._refresh_quote_data()
        for stock, price in p_initial_prices.items():
            self.dict_quote_data[stock] = quote_data(p_ltp=float(price))
        self._record_ltp_high_watermarks({
            stock: self.dict_quote_data[stock]
            for stock in p_initial_prices
            if stock in self.dict_quote_data
        })

    def get_option_chain_snapshot(self, underlying):
        """Fetch one shared option-chain snapshot for concurrent strategy startup threads."""
        if self.trade_utility is None:
            raise RuntimeError("Trade utility is not configured")
        with self._option_chain_lock:
            if underlying not in self._option_chain_cache:
                self._option_chain_cache[underlying] = (
                    self.trade_utility.get_broker_utility().getOptionChain(underlying))
            chain_df, call_oi, put_oi = self._option_chain_cache[underlying]
            return chain_df.copy(), call_oi, put_oi

    def _refresh_quote_data(self):
        if self.quote_source == "broker":
            quote_data_by_symbol = self.trade_utility.get_broker_utility().get_quotes(
                self.lst_get_quote_req)
        else:
            quote_data_by_symbol = self._get_websocket_quote_data()
        self._record_ltp_high_watermarks(quote_data_by_symbol)
        self.dict_quote_data.update(quote_data_by_symbol)

    def _get_websocket_quote_data(self):
        data_websocket = self._get_data_websocket()
        if data_websocket is None:
            return {}
        ticks = data_websocket.get_tick_data()
        if ticks is None or ticks.empty or "symbol" not in ticks.columns:
            return {}

        quote_data_by_symbol = {}
        for quote_request in self.lst_get_quote_req:
            websocket_symbol = self._get_websocket_symbol(quote_request)
            if not websocket_symbol:
                continue
            symbol_ticks = ticks.loc[ticks["symbol"].astype(str) == websocket_symbol]
            if symbol_ticks.empty:
                continue
            tick = symbol_ticks.iloc[-1]
            ltp = self._tick_value(tick, "ltp")
            if ltp is None:
                continue
            quote_data_by_symbol[quote_request.symbol] = quote_data(
                p_ask=self._tick_value(tick, "ask_price", "ask", default=0.0),
                p_open=self._tick_value(tick, "open_price", "open", default=0.0),
                p_high=self._tick_value(tick, "high_price", "high", default=ltp),
                p_low=self._tick_value(tick, "low_price", "low", default=ltp),
                p_prev_close=self._tick_value(tick, "prev_close_price", "prev_close", default=0.0),
                p_ltp=ltp,
                p_volume=self._tick_value(tick, "vol_traded_today", "volume", default=0),
            )
        return quote_data_by_symbol

    @staticmethod
    def _tick_value(tick, *columns, default=None):
        for column in columns:
            if column in tick.index and pd.notna(tick[column]):
                try:
                    return float(tick[column])
                except (TypeError, ValueError):
                    continue
        return default

    def remove_stock(self, p_str_stock):
        index = 0
        removed_quote_request = None
        for quote_req_data in self.lst_get_quote_req:
            if p_str_stock == quote_req_data.symbol:
                removed_quote_request = self.lst_get_quote_req.pop(index)
                break
            index = index + 1

        if p_str_stock in self.lst_stocks:
            self.lst_stocks.remove(p_str_stock)

        if removed_quote_request is not None and self.data_websocket is not None:
            symbol = self._get_websocket_symbol(removed_quote_request)
            if symbol:
                self.data_websocket.unsubscribe([symbol])

    def get_quote_data(self):
        return self.dict_quote_data

    def fetchOHLC(self, ticker, str_from_date, str_to_date, interval,
                  all_data=False, exchange="NSE", market_type="EQ", source=None):
        """Fetch candles from WebSocket ticks or the configured broker utility."""
        if self.trade_utility is None:
            raise RuntimeError("Trade utility is not configured")
        candle_source = self._normalize_candle_source(source or self.candle_source)
        if candle_source == "broker":
            broker_utility = self.trade_utility.get_broker_utility()
            get_ohlc = getattr(broker_utility, "getOHLC", None)
            if not callable(get_ohlc):
                get_ohlc = getattr(broker_utility, "fetchOHLC", None)
            if not callable(get_ohlc):
                raise AttributeError("Broker utility does not expose getOHLC or fetchOHLC")
            return get_ohlc(
                ticker=ticker,
                str_from_date=str_from_date,
                str_to_date=str_to_date,
                interval=interval,
                all_data=all_data,
                exchange=exchange,
                market_type=market_type,
            )

        interval_minutes = self._interval_minutes(interval)

        if ticker not in self.lst_stocks:
            self.add_stocks([ticker], [market_type])

        websocket_symbol = self._get_websocket_symbol(
            get_quote_request_data(p_symbol=ticker, p_market_type=market_type))
        if websocket_symbol is None:
            return self.fyers_candle_utility.build_5min_candles(pd.DataFrame(), [ticker])[ticker]

        candle_data = self.fyers_candle_utility.build_5min_candles(
            self.get_tick_data(), [websocket_symbol], interval_minutes).get(websocket_symbol)
        if candle_data is None or candle_data.empty:
            return self.fyers_candle_utility.build_5min_candles(
                pd.DataFrame(), [websocket_symbol])[websocket_symbol]

        start = pd.Timestamp(str_from_date)
        end = pd.Timestamp(str_to_date)
        if start.tzinfo is not None:
            start = start.tz_convert("Asia/Kolkata").tz_localize(None)
        if end.tzinfo is not None:
            end = end.tz_convert("Asia/Kolkata").tz_localize(None)
        return candle_data.loc[
            (candle_data[DATE_TIME] >= start) & (candle_data[DATE_TIME] <= end)
        ].reset_index(drop=True)

    @staticmethod
    def _interval_minutes(interval):
        normalized_interval = str(interval).lower().replace(" ", "")
        for suffix in ("minutes", "minute", "mins", "min", "m"):
            if normalized_interval.endswith(suffix):
                normalized_interval = normalized_interval[:-len(suffix)]
                break
        try:
            interval_minutes = int(normalized_interval)
        except ValueError as error:
            raise ValueError("WebSocket candles require an interval in minutes") from error
        if interval_minutes <= 0:
            raise ValueError("WebSocket interval must be a positive number of minutes")
        return interval_minutes

    @staticmethod
    def _normalize_candle_source(source):
        normalized_source = str(source).strip().lower()
        if normalized_source not in {"websocket", "broker"}:
            raise ValueError("candle_source must be 'websocket' or 'broker'")
        return normalized_source

    @staticmethod
    def _normalize_quote_source(source):
        normalized_source = str(source).strip().lower()
        if normalized_source not in {"websocket", "broker"}:
            raise ValueError("quote_source must be 'websocket' or 'broker'")
        return normalized_source

    def get_tick_data(self):
        """Return the broker's accumulated raw tick snapshot, if available."""
        if self.data_websocket is None:
            return pd.DataFrame()
        return self.data_websocket.get_tick_data()

    def get_5min_candle_data(self):
        """Return candle frames keyed by the same bare symbols as REST quotes."""
        if self.data_websocket is None:
            return {}

        dict_quote_symbols = {}
        for quote_req_data in self.lst_get_quote_req:
            websocket_symbol = self._get_websocket_symbol(quote_req_data)
            if websocket_symbol:
                dict_quote_symbols[websocket_symbol] = quote_req_data.symbol

        dict_fyers_candles = self.fyers_candle_utility.build_5min_candles(
            self.data_websocket.get_tick_data(), list(dict_quote_symbols))
        return {quote_symbol: dict_fyers_candles[websocket_symbol]
                for websocket_symbol, quote_symbol in dict_quote_symbols.items()}
    
    def _record_ltp_high_watermarks(self, quote_data):
        with self._quote_lock:
            for symbol, quote in quote_data.items():
                ltp = float(quote.ltp)
                if ltp > 0:
                    self._ltp_high_watermarks[symbol] = max(
                        ltp, self._ltp_high_watermarks.get(symbol, ltp))

    def get_ltp_high_watermark(self, symbol):
        with self._quote_lock:
            return self._ltp_high_watermarks.get(symbol)

    def reset_ltp_high_watermark(self, symbol):
        quote = self.dict_quote_data.get(symbol)
        ltp = float(quote.ltp) if quote is not None else 0.0
        with self._quote_lock:
            if ltp > 0:
                self._ltp_high_watermarks[symbol] = ltp
            else:
                self._ltp_high_watermarks.pop(symbol, None)

    def stop(self):
        """Stop the quote polling loop and close the optional market-data stream."""
        self.is_stopped = True
        self.stop_event.set()
        if self.data_websocket is not None:
            self.data_websocket.close()
