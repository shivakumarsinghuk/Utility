# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

from Utility.utility import *
import datetime as dt
import pandas_market_calendars as mcal
from selenium import webdriver
from selenium.webdriver.common.by import By
import traceback
import time
from datetime import timedelta


dict_option_name_to_index = {"NIFTY":"NIFTY50", "BANKNIFTY":"NIFTYBANK"}
dict_fno_lot_size = {"NIFTY50":75, "NIFTY":75, "NIFTYBANK":35}

class nse_utitlity:
    def __init__(self):
        #self.dict_lot_size = nse_get_fno_lot_sizes()
        self.dict_monthly_expiry_date = {}
        #self.__get_monthly_expiry_date()
        self.dict_expiry_date = {}

    def get_last_trading_date(self):
        data = nse_quote("SBIN")['opt_timestamp'].split(" ")[0]
        return conver_date_format(data)

    def get_index_expiry_date(self, option_name="BANKNIFTY", preset=0):
        #return "24-Dec-2024", "23-Oct-2024", "29-Jan-2025"

        #if the data is stored in dictionary, return the data from dictionary
        if option_name in self.dict_expiry_date:
            return self.dict_expiry_date[option_name]

        monthly_expiry_date = ""
        is_current_week_monthly_expiry = False
        is_next_week_monthly_expiry = False

        if option_name == "NIFTY":
            lst_expiry_dates = generate_weekly_expiry_dates(datetime.now() + timedelta(preset), 1)
        else:
            lst_expiry_dates = generate_monthly_expiry_dates(datetime.now() + timedelta(preset), 1)

        current_week_expiry_date = lst_expiry_dates[0]
        next_week_expiry_date = lst_expiry_dates[1]
        if not current_week_expiry_date.split("-")[1] == next_week_expiry_date.split("-")[1]:
            is_current_week_monthly_expiry = True

        if not next_week_expiry_date.split("-")[1] == lst_expiry_dates[2].split("-")[1]:
            is_next_week_monthly_expiry = True

        # update is expiry day
        is_expiry_day = (
                    current_week_expiry_date == (dt.date.today() - timedelta(days=preset)).strftime("%d-%b-%Y"))

        print("is_current_week_monthly_expiry: ", is_current_week_monthly_expiry)
        if is_current_week_monthly_expiry:
            monthly_expiry_date = current_week_expiry_date
        elif is_next_week_monthly_expiry:
            monthly_expiry_date = next_week_expiry_date
        else:
            # Monthly expiry date is extracted by parsing through expiry dates
            for index in range(0, len(lst_expiry_dates) - 1):
                if not lst_expiry_dates[index].split("-")[1] == \
                       lst_expiry_dates[index + 1].split("-")[1]:
                    monthly_expiry_date = lst_expiry_dates[index]
                    break

        self.dict_expiry_date[
            option_name] = current_week_expiry_date, next_week_expiry_date, monthly_expiry_date, is_expiry_day, is_current_week_monthly_expiry, is_next_week_monthly_expiry
        return current_week_expiry_date, next_week_expiry_date, monthly_expiry_date, is_expiry_day, is_current_week_monthly_expiry, is_next_week_monthly_expiry


    def get_lot_size(self, p_symbol):
        fno_data = nse_fno(p_symbol)
        print(fno_data['underlyingInfo'])

        for key, value in nse_fno(p_symbol).items():
            print(key)

    def get_prev_day_trade_date(self, preset=0):
        str_start_date = (dt.date.today() - timedelta(days=preset + 30)).strftime('%Y-%m-%d')
        str_end_date = (dt.date.today() - timedelta(days=preset)).strftime('%Y-%m-%d')
        #get the trade dates
        nyse = mcal.get_calendar('NSE')
        prev_date_object = nyse.schedule(start_date=str_start_date, end_date=str_end_date)[::-1]['market_open'].values[1]
        return (str(prev_date_object)).split("T")[0]

    def get_index_name_by_option_name(self, p_optionname:str):
        #check whether option name is in dict
        if p_optionname in dict_option_name_to_index:
            return dict_option_name_to_index[p_optionname]
        else:
            return p_optionname

    def get_fno_lot_size(self,p_optionname:str):
        print("Getting lot size for: ", p_optionname)
        if p_optionname in dict_fno_lot_size:
            print("Getting from dictionary")
            return dict_fno_lot_size[p_optionname]
        else:
            return 0

    def is_monthly_expiry(self, p_str_option_name):
        option_index = get_position_of_first_digit(p_str_option_name)
        if p_str_option_name[0:option_index] in self.dict_monthly_expiry_date:
            lst_monthly_expiry_date = self.dict_monthly_expiry_date[p_str_option_name[0:option_index]].split("-")
            monthly_expiry_date = lst_monthly_expiry_date[0] + lst_monthly_expiry_date[1].upper() + lst_monthly_expiry_date[2][2:]
            if p_str_option_name[option_index:(option_index + 7)] \
                == monthly_expiry_date:
                return True
            else:
                return False
        else:
            return True

    def __get_monthly_expiry_date(self):
        driver = webdriver.Chrome()
        url = 'https://www.nseindia.com/get-quotes/derivatives?symbol=BANKNIFTY'
        driver.get(url)
        time.sleep(5)
        url = 'https://www.nseindia.com/get-quotes/derivatives?symbol=NIFTY'
        driver.get(url)
        time.sleep(5)
        # Get all text from the body
        body_text = driver.find_element(By.TAG_NAME, 'body').text
        for index in range(1, 10):
            if not body_text.split('Expiry Date')[1].split('\n')[index].split("-")[1] == \
                    body_text.split('Expiry Date')[1].split('\n')[index + 1].split("-")[1]:
                break
        self.dict_monthly_expiry_date["NIFTY"] = body_text.split('Expiry Date')[1].split('\n')[index].upper()


#for testing

# Create a calendar
'''
obj_nse_utility = nse_utitlity()
print(obj_nse_utility.get_prev_day_trade_date(3))

#obj_nse_utility.is_monthly_expiry()
print(obj_nse_utility.is_monthly_expiry("NIFTY28OCT2554600CE"))


print(obj_nse_utility.get_index_expiry_date())
dict_option_expiry_data = {}
dict_option_expiry_data["NIFTY"] = obj_nse_utility.get_index_expiry_date("NIFTY")

#dict_option_expiry_data["BANKNIFTY"] = obj_nse_utility.get_index_expiry_date("BANKNIFTY")
print(dict_option_expiry_data["NIFTY"])
print(dict_option_expiry_data["NIFTY"][0])

print(obj_nse_utility.get_fno_lot_size("BANKNIFTY"))

print(obj_nse_utility.get_index_name_by_option_name("BANKNIFTY"))
print(obj_nse_utility.get_last_trading_date())
#print(nse_quote("BANKNIFTY"))
print(obj_nse_utility.get_index_expiry_date())
print(capital_market.index_data('NIFTY BANK', period='1M'))
'''