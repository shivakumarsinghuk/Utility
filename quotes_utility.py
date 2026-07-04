# -*- coding: utf-8 -*-


import threading
from broker_platform.pal.utility_manager import *
import time

class QuoteUtility:
    def __init__(self, p_trade_utility, p_interval=2):
        self.trade_utility = p_trade_utility
        self.lst_stocks = []
        self.lst_get_quote_req = []
        self.interval = p_interval
        self.execute_thread = threading.Thread(target=self.execute)
        self.dict_quote_data = {}
        self.is_stopped = False

        # start the thread
        self.execute_thread.start()

    def get_thread_info(self):
        return self.execute_thread

    def execute(self):
        time.sleep(self.interval)
        while not self.is_stopped:
            #check whether stocks list having atleast one stock
            if len(self.lst_stocks) > 0:
                time.sleep(4)
                self.dict_quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)
        print("Getquote Stopped")

    def add_stocks(self, p_lst_stocks, p_lst_market_type):
        for index, stock in enumerate(p_lst_stocks):
            if not stock in self.lst_stocks:
                self.lst_stocks.append(stock)
                obj_get_quotes_req_data = get_quote_request_data(p_symbol=stock, p_market_type=p_lst_market_type[index])
                self.lst_get_quote_req.append(obj_get_quotes_req_data)
        #updare the dict quote data
        self.dict_quote_data = self.trade_utility.get_broker_utility().get_quotes(self.lst_get_quote_req)

    def remove_stock(self, p_str_stock):
        index = 0
        for quote_req_data in self.lst_get_quote_req:
            if p_str_stock == quote_req_data.symbol:
                self.lst_get_quote_req.pop(index)
                break
            index = index + 1

    def get_quote_data(self):
        return self.dict_quote_data

    def stop(self):
        self.is_stopped = True