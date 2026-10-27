# -*- coding: utf-8 -*-


import threading
from BrokerUtility.pal.utility_manager import *
import pandas as pd

from .fyers_candle_utility import FyersCandleUtility

class QuoteUtility:
    def __init__(self, p_interval=2):
        self.trade_utility = None
        self.lst_stocks = []
        self.lst_get_quote_req = []
        self.interval = p_interval
        self.execute_thread = threading.Thread(target=self.execute)
        self.dict_quote_data = {}
        self.is_stopped = False
        self.stop_event = threading.Event()
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
                    self.dict_quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)
            else:
                self.stop_event.wait(self.interval)
        print("Getquote Stopped")

    def _get_data_websocket(self):
        if self.data_websocket is not None or self.trade_utility is None:
            return self.data_websocket

        broker_utility = self.trade_utility.get_broker_utility()
        get_data_websocket = getattr(broker_utility, "get_data_websocket", None)
        if callable(get_data_websocket):
            self.data_websocket = get_data_websocket()
        return self.data_websocket

    def _get_websocket_symbol(self, p_quote_req_data):
        if self.trade_utility is None:
            return None
        broker_utility = self.trade_utility.get_broker_utility()
        get_data_websocket_symbol = getattr(broker_utility, "get_data_websocket_symbol", None)
        if not callable(get_data_websocket_symbol):
            return None
        return get_data_websocket_symbol(p_quote_req_data.symbol,
                                         p_quote_req_data.market_type)

    def add_stocks(self, p_lst_stocks, p_lst_market_type):
        lst_new_quote_requests = []
        for index, stock in enumerate(p_lst_stocks):
            if not stock in self.lst_stocks:
                self.lst_stocks.append(stock)
                obj_get_quotes_req_data = get_quote_request_data(p_symbol=stock, p_market_type=p_lst_market_type[index])
                self.lst_get_quote_req.append(obj_get_quotes_req_data)
                lst_new_quote_requests.append(obj_get_quotes_req_data)
        #updare the dict quote data
        self.dict_quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)

        if lst_new_quote_requests:
            data_websocket = self._get_data_websocket()
            if data_websocket is not None:
                lst_symbols = [self._get_websocket_symbol(quote_req)
                               for quote_req in lst_new_quote_requests]
                lst_symbols = [symbol for symbol in lst_symbols if symbol]
                if lst_symbols:
                    data_websocket.subscribe(lst_symbols)

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

    def get_tick_data(self):
        if self.data_websocket is None:
            return pd.DataFrame()
        return self.data_websocket.get_tick_data()

    def get_5min_candle_data(self):
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

    def stop(self):
        self.is_stopped = True
        self.stop_event.set()
        if self.data_websocket is not None:
            self.data_websocket.close()
