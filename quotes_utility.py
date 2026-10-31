# -*- coding: utf-8 -*-


import threading
from BrokerUtility.pal.utility_manager import *
import time

class QuoteUtility:
    def __init__(self, p_interval=2):
        self.trade_utility = None
        self.lst_stocks = []
        self.lst_get_quote_req = []
        self.interval = p_interval
        self.execute_thread = threading.Thread(target=self.execute)
        self.dict_quote_data = {}
        self._ltp_high_watermarks = {}
        self._quote_lock = threading.Lock()
        self.is_stopped = False

        # start the thread
        self.execute_thread.start()


    def set_trade_utility(self, p_trade_utility):
        if self.trade_utility is None:
            self.trade_utility = p_trade_utility

    def get_thread_info(self):
        return self.execute_thread

    def execute(self):
        time.sleep(self.interval)
        while not self.is_stopped:
            #check whether stocks list having atleast one stock
            if len(self.lst_stocks) > 0:
                time.sleep(4)
                if self.trade_utility:
                    quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)
                    self._record_ltp_high_watermarks(quote_data)
                    self.dict_quote_data = quote_data
        print("Getquote Stopped")

    def add_stocks(self, p_lst_stocks, p_lst_market_type):
        for index, stock in enumerate(p_lst_stocks):
            if not stock in self.lst_stocks:
                self.lst_stocks.append(stock)
                obj_get_quotes_req_data = get_quote_request_data(p_symbol=stock, p_market_type=p_lst_market_type[index])
                self.lst_get_quote_req.append(obj_get_quotes_req_data)
        #updare the dict quote data
        quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)
        self._record_ltp_high_watermarks(quote_data)
        self.dict_quote_data = quote_data

    def remove_stock(self, p_str_stock):
        index = 0
        for quote_req_data in self.lst_get_quote_req:
            if p_str_stock == quote_req_data.symbol:
                self.lst_get_quote_req.pop(index)
                break
            index = index + 1

    def get_quote_data(self):
        return self.dict_quote_data

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
        self.is_stopped = True