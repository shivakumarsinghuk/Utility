# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""

import datetime
from nsepython import *
import pywhatkit
import pyautogui
#import datetime
from pynput.keyboard import Key, Controller
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from math import floor
from decimal import *
from collections import defaultdict
#from termcolor import colored as cl
import calendar
from datetime import timedelta
from datatypes.trade_data import *

#cwd = os.chdir("C:/1Ravee/PythonAlgo/authenticate")
#defines
TRADE_START_MIN = 15
FIFTY_NINE_MIN = 59
SIXTY_MIN = 60

holidays = [
    "26-01-2026",
    "03-03-2026",
    "26-03-2026",
    "31-03-2026",
    "03-04-2026",
    "14-04-2026",
    "01-05-2026",
    "28-05-2026",
    "26-06-2026",
    "14-09-2026",
    "02-10-2026",
    "20-10-2026",
    "10-11-2026",
    "14-11-2026",
    "25-12-2026",
]

holidays = [datetime.strptime(h, "%d-%m-%Y") for h in holidays]

#Utiligty functions
def nested_dict():
    return defaultdict(nested_dict)

def extract_week_day_config_data(data, start_row, end_row):
    rows = data[start_row:end_row]
    specific_cells = [[row[0], row[1], row[2], row[3], row[4]] for row in rows]
    data_dict = nested_dict()
    # Print result
    for row in specific_cells:

        data_dict[row[0]][row[1]][row[2]][row[3]] = {'Pivot Condition': row[4]}
    return data_dict

def retrieve_week_day_config_by_keys(data, week_day, index_type, option_type, candle_type):
    return data[week_day][index_type][option_type][candle_type]


def get_week_day_by_date(pdate):
    return pdate.strftime("%A").upper()

def get_position_of_first_digit(p_strInput:str):
    for i, ch in enumerate(p_strInput):
        if ch.isdigit():
            return i

def get_option_name_details(p_strInput:str):
    digit_position = get_position_of_first_digit(p_strInput)
    index_type = p_strInput[:digit_position]
    expiry_date = p_strInput[digit_position:(digit_position + 2)] \
                  + "-" + p_strInput[(digit_position + 2):(digit_position + 5)]\
                  + "-" + p_strInput[(digit_position + 5):(digit_position + 7)]
    option_price = p_strInput[(digit_position + 7):(digit_position + 12)]
    option_type = p_strInput[(digit_position + 12):(digit_position + 14)]
    return index_type, expiry_date, option_price, option_type

def generate_option_name(index_type:str, expiry_date:str, option_price:str, option_type:str):
    date_split = expiry_date.split("-")
    return index_type + date_split[0] + date_split[1].upper() + date_split[2][2:] + option_price + option_type


def generate_weekly_expiry_dates(p_date, expiry_day):
    expiry_dates = []
    start_date = datetime(p_date.year, p_date.month, p_date.day)
    end_date = datetime(p_date.year, 12, 31)

    while start_date.weekday() != 1:  # Find the target weekday
        start_date += timedelta(days=expiry_day)

    while start_date <= end_date:
        if start_date not in holidays:
            expiry_dates.append(start_date.strftime("%d-%b-%Y").upper())
        else:  # If expiry day is a holiday, use previous trading day
            adjusted_expiry_date = start_date - timedelta(days=1)
            while adjusted_expiry_date in holidays:
                adjusted_expiry_date -= timedelta(days=1)
            expiry_dates.append(adjusted_expiry_date.strftime("%d-%b-%Y").upper())

        start_date += timedelta(weeks=1)

    return expiry_dates


def generate_monthly_expiry_dates(p_date, p_expiry_day):
    expiry_dates = []

    for month in range(p_date.month, 13):
        # Get last day of the month
        last_day = calendar.monthrange(p_date.year, month)[1]
        date = datetime(p_date.year, month, last_day)

        # Move backwards until expiry weekday (Tuesday = 1 as per your code)
        while date.weekday() != p_expiry_day:
            date -= timedelta(days=1)

        # If expiry day is a holiday, move to previous trading day
        adjusted_date = date
        if adjusted_date in holidays:
            adjusted_date -= timedelta(days=1)
            while adjusted_date in holidays:
                adjusted_date -= timedelta(days=1)

        # FORMAT CHANGE HERE
        expiry_dates.append(adjusted_date.strftime("%d-%b-%Y").upper())

    return expiry_dates




def get_modulus_time_by_interver(str_interval):
    dict_time_to_string = {}
    dict_time_to_string["minute"] = "%M"
    dict_time_to_string["hour"] = "%H"
    interval_value, interval_type = separate_numbers_text_in_string(str_interval)
    interval_value = int(interval_value)
    print(int(datetime.now().time().strftime(dict_time_to_string[interval_type])))
    i_modulus_time = int(datetime.now().time().strftime(dict_time_to_string[interval_type])) % interval_value
    return i_modulus_time

def get_next_trade_remaining_time(i_interval_value, str_interval_type):
    dict_func = {}
    dict_func["minute"] = get_next_trade_remaining_time_for_min
    dict_func["hour"] = get_next_trade_remaining_time_for_hour
    i_remaining_time = dict_func[str_interval_type](i_interval_value)
    return i_remaining_time

def get_next_trade_remaining_time_for_min(i_interval_value):
    return int(i_interval_value) * 60

def get_next_trade_remaining_time_for_hour(i_interval_value):
    return int(i_interval_value) * 60 * 60

def separate_numbers_text_in_string(str_input):
    # Using re.compile() + re.match() + re.groups()
    # Splitting text and number in string
    match = re.match(r"([0-9]+)([a-z]+)", str_input, re.I)
    if match:
        items = match.groups()
    return items[0], items[1]

def get_buffer_entry_price(transaction_type, entry_price, buffer_percentage):
    transaction_type = transaction_type.lower()
    buffer_percentage = (buffer_percentage/100)
    buffer_entry_price = (entry_price + (entry_price * buffer_percentage)) if transaction_type == "buy" \
                         else (entry_price - (entry_price * buffer_percentage))
    buffer_entry_price = math.ceil(buffer_entry_price/0.05) * 0.05 if transaction_type == "buy" \
                         else math.floor(buffer_entry_price/0.05) * 0.05
    trigger_price = (buffer_entry_price - 0.05) if transaction_type == "buy" else (buffer_entry_price + 0.05)
    buffer_entry_price = round(buffer_entry_price, 2)
    trigger_price = round(trigger_price, 2)
    return buffer_entry_price, trigger_price

def isCandleTypeValid(candle_type):
    isValid = False
    if candle_type == "GREEN" or candle_type == "RED":
        isValid = True
    return isValid

#loss will be in rupees, stop loss will be in % of entry price
def calculate_quantity_by_loss_sl(entry_price, loss, stop_loss):
    quantity = 1
    if entry_price > 0 and loss > 0 and stop_loss > 0:
        quantity = loss/calculate_percentage_value(entry_price, stop_loss)
    if quantity <= 0:
        quantity = 1
    return int(quantity)

def calculate_percentage_value(number, percentage):
    percentage_value = 0.0
    if number > 0 and percentage > 0:
        percentage_value = (float(number)*float(percentage))/100
    return percentage_value

def is_trade_start_time_expired(start_time, i_interval_value=0, str_interval_type="minute"):
    is_start_time_expired = False
    if (datetime.now().time() > start_time.time()):
        print(datetime.now().time(), start_time.time())
        i_remaining_time = get_next_trade_remaining_time(i_interval_value, str_interval_type)
        if (datetime.now() - start_time).seconds > i_remaining_time:
            is_start_time_expired = True
    return is_start_time_expired

def get_lot_size(symbol):
    i_lot_size = 0
    if symbol in dict_lot_size:
        i_lot_size = int(dict_lot_size[symbol])
    return i_lot_size

def get_next_expiry_date(indice):
    payload = nse_optionchain_scrapper(indice)
    currentExpiry, dte = nse_expirydetails(payload, 0)
    current_expiry_date = currentExpiry.strftime("%Y-%m-%d")
    next_expiry, dte = nse_expirydetails(payload, 1)
    next_expiry_date = next_expiry.strftime("%Y-%m-%d")
    #compare the months
    current_expiry_month = current_expiry_date.split("-")[1]
    next_expiry_month = next_expiry_date.split("-")[1]
    is_month_expiry = False
    if not current_expiry_month == next_expiry_month:
        is_month_expiry = True
    return current_expiry_date, is_month_expiry

def conver_date_format(date):
    Months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    string = date.split("-")

    year = string[2]
    day = string[0]

    if len(day) < 2:
        day = "0" + day

    month = str(Months.index(string[1]) + 1)

    if len(month) < 2:
        month = "0" + month

    return "{0}-{1}-{2}".format(year, month, day)

def compute_camarilla_h4(candle_data):
    try:
        h4 = (0.55 * (candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0])) + candle_data[CLOSE_PRICE].values[0]
        return round(math.floor(h4/0.05) * 0.05, 2)
    except:
        print("Exception while computing h4")

def compute_pivot_point_r1(candle_data):
    try:
        #formula to calculate pivot point r1
        #pp = (h + l + c) / 3;
        #r1 = 2 * pp – l;
        pivot_point = (candle_data[HIGH_PRICE].values[0] + \
                      candle_data[LOW_PRICE].values[0] + \
                      candle_data[CLOSE_PRICE].values[0]) / 3
        r1 = 2 * pivot_point - candle_data[LOW_PRICE].values[0]
        return round(math.floor(r1/0.05) * 0.05, 2)
    except:
        print("Exception while computing h4")

def compute_vwap(candle_data, last_loc=0):
    cum_typical_price = 0.0
    #for testing
    if last_loc > 0:
        candle_data = candle_data[0:last_loc]
    #calculate cumulative typical price
    for i_index in range(len(candle_data)):
        # calculation typical price, typical price = (H+L+C)/3
        typical_price = (candle_data[HIGH_PRICE].values[i_index] + \
                         candle_data[LOW_PRICE].values[i_index] + \
                         candle_data[CLOSE_PRICE].values[i_index]) / 3
        typical_price = typical_price * candle_data[VOLUME_DATA].values[i_index]
        cum_typical_price = cum_typical_price + typical_price

    #divide by current volume
    volume_col_data = candle_data[VOLUME_DATA].copy()
    pd_cum_sum = volume_col_data.cumsum(axis=0)
    cum_vol = pd_cum_sum.loc[pd_cum_sum.index[-1]]
    #vwap is cumulative of typical price * cumulative of volume
    #round off to 2 decimals
    vwap = round((cum_typical_price / cum_vol), 2)
    return vwap

def compute_pivot_cpr(candle_data):
    pivot_point = 0.0
    bottom_cpr = 0.0
    top_cpr = 0.0
    bc = 0.0
    tc = 0.0
    try:
        #formula to calculate pivot point r1
        #pp = (h + l + c) / 3;
        #r1 = 2 * pp – l;
        #Pivot = (High + Low + Close) ÷ 3.
        #Bottom CPR = (High + Low) ÷ 2.
        #Top CPR = (Pivot - BC) + Pivot.
        pivot_point = (candle_data[HIGH_PRICE].values[0] + \
                      candle_data[LOW_PRICE].values[0] + \
                      candle_data[CLOSE_PRICE].values[0]) / 3
        bc = (candle_data[HIGH_PRICE].values[0] + \
                      candle_data[LOW_PRICE].values[0]) / 2
        tc = (pivot_point - bc) + pivot_point

        if bc > tc:
            top_cpr = bc
            bottom_cpr = tc
        else:
            top_cpr = tc
            bottom_cpr = bc
    except:
        print("Exception while computing h4")
    return top_cpr, pivot_point, bottom_cpr

def compute_diff_percentage(f_value1, f_value2, non_negative=False):
    diff_percentage = 0.0
    if non_negative:
        if f_value1 > f_value2:
            diff_percentage = ((f_value1 - f_value2)/f_value1)*100
        elif f_value2 > f_value1:
            diff_percentage = ((f_value2 - f_value1)/f_value1)*100
    else:
            diff_percentage = ((f_value1 - f_value2)/f_value1)*100
    return diff_percentage

def compute_camarilla_data(candle_data):
    rvalues = [0.0,0.0,0.0,0.0,0.0,0.0]
    svalues = [0.0,0.0,0.0,0.0,0.0,0.0]
    pivot = 0.0
    #               R1-L1, R2-L2, R3-L3, R4-L4
    pivot_points = [0.0916, 0.183, 0.275, 0.55]
    try:
        if candle_data[HIGH_PRICE].values[0] > 0 and candle_data[LOW_PRICE].values[0] > 0 \
            and candle_data[CLOSE_PRICE].values[0] > 0:
            rvalues.clear()
            svalues.clear()
            #calculate R1-R4 and S1-S4
            pivot = (candle_data[HIGH_PRICE].values[0] + candle_data[LOW_PRICE].values[0] +
                     candle_data[CLOSE_PRICE].values[0]) / 3
            for pivot_point in pivot_points:
                rvalues.append((pivot_point * (candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0])) + candle_data[CLOSE_PRICE].values[0])
                svalues.append(candle_data[CLOSE_PRICE].values[0] - (pivot_point * (candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0])))
            #calculate R5 and S5
            '''
            rvalues.append((candle_data[HIGH_PRICE].values[0]/candle_data[LOW_PRICE].values[0]) * \
                           candle_data[CLOSE_PRICE].values[0])
            svalues.append(candle_data[CLOSE_PRICE].values[0] - (rvalues[4] - candle_data[CLOSE_PRICE].values[0]))
            '''
            rvalues.append(candle_data[CLOSE_PRICE].values[0] + (candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0]) * 0.7)
            svalues.append(candle_data[CLOSE_PRICE].values[0] - (
                        candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0]) * 0.7)
            #Calculate R6 and S6
            '''
            rvalues.append(rvalues[4] + 1.168 * (rvalues[4] - rvalues[3]))
            svalues.append(candle_data[CLOSE_PRICE].values[0] - (rvalues[5] - candle_data[CLOSE_PRICE].values[0]))
            '''
            rvalues.append(candle_data[CLOSE_PRICE].values[0] + (candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0]) * 0.855)
            svalues.append(candle_data[CLOSE_PRICE].values[0] - (
                        candle_data[HIGH_PRICE].values[0] - candle_data[LOW_PRICE].values[0]) * 0.855)
    except:
        print("Exception while computing h4")
    return rvalues, pivot, svalues

def compute_super_trend(candle_data):
    super_trend = 0.0
    return super_trend

def compute_wick_size(open, high, low, close, candle_type):
    wick_size_top = 0.0
    wick_size_bottom = 0.0
    if "GREEN" == candle_type:
        wick_size_top = compute_diff_percentage(high, close)
        # get the bottom wick size
        wick_size_bottom = compute_diff_percentage(open, low)
    else:
        wick_size_top = compute_diff_percentage(high, open)
        # get the bottom wick size
        wick_size_bottom = compute_diff_percentage(close, low)

    return wick_size_top, wick_size_bottom

def compute_candle_size(high, low):
    candle_size = 0.0
    if high > 0 and low > 0:
        candle_size = (high-low)/high * 100
    return candle_size

def compute_rsi(stock_data, periods=14):
    lst_gain = []
    lst_loss = []
    current_day_gain = 0.0
    current_day_loss = 0.0
    rsi = 0.0
    if periods < len(stock_data):
        # print("Length: ", len(stock_data))
        for index in range(periods):
            i_gain = stock_data[CLOSE_PRICE].values[index + 1] - stock_data[CLOSE_PRICE].values[index + 2]
            if i_gain > 0:
                lst_gain.append(i_gain)
            else:
                lst_gain.append(0)
            i_loss = stock_data[CLOSE_PRICE].values[index + 2] - stock_data[CLOSE_PRICE].values[index + 1]
            if i_loss > 0:
                lst_loss.append(i_loss)
            else:
                lst_loss.append(0)
        # print("lst_gain: ", lst_gain)
        avg_gain = round(sum(lst_gain) / len(lst_gain), 2)
        avg_loss = round(sum(lst_loss) / len(lst_loss), 2)
        # print("avg_gain: ", avg_gain)
        # print("avg_loss: ", avg_loss)
        # calculate current day gain
        current_day_gain = stock_data[CLOSE_PRICE].values[0] - stock_data[CLOSE_PRICE].values[1]
        if current_day_gain < 0:
            current_day_gain = 0
        # print("current_day_gain: ", current_day_gain)

        # print("current_day_avg_gain: ", current_day_avg_gain)
        # calculate current day loss
        current_day_loss = stock_data[CLOSE_PRICE].values[1] - stock_data[CLOSE_PRICE].values[0]
        if current_day_loss < 0:
            current_day_loss = 0
        # print("current_day_loss: ", current_day_loss)

        # calculate current day average gain
        if len(stock_data) > (periods + 2):
            previous_day_avg_gain, previous_day_avg_loss, rsi = compute_rsi(stock_data[1:len(stock_data)],
                                                                                 periods)
            current_day_avg_gain = ((previous_day_avg_gain * (periods - 1)) + current_day_gain) / periods
            current_day_avg_loss = ((previous_day_avg_loss * (periods - 1)) + current_day_loss) / periods
        else:
            current_day_avg_gain = ((avg_gain * (periods - 1)) + current_day_gain) / periods
            current_day_avg_loss = ((avg_loss * (periods - 1)) + current_day_loss) / periods
        # print("current_day_avg_loss: ", current_day_avg_loss)
        rsi = (current_day_avg_gain / current_day_avg_loss)
        rsi = 100 - 100 / (1 + rsi)
    else:
        print("Invalid stock data. Periods is more than stock data length")
    return current_day_avg_gain, current_day_avg_loss, round(rsi, 2)

def send_whatsapp_message(str_number, str_message):
    #pywhatkit.sendwhatmsg(phone_no=str_number, message=str_message, time_hour=8, time_min=21,tab_close=True)
    pywhatkit.sendwhatmsg_instantly(phone_no=str_number,message=str_message,wait_time=10,tab_close=True,close_time=10)
    time.sleep(10)
    pyautogui.click()
    time.sleep(1)
    Controller().press(Key.enter)
    Controller().release(Key.enter)
    time.sleep(1)
    print("Message sent!")

def get_end_date_by_periods(start_date, i_period = 25):
    time_delta = timedelta(days = i_period)
    end_date = start_date - time_delta
    return end_date

def get_time_index_from_pd_column(date_time_column, str_time):
    index = 0
    for values in date_time_column.values:
        if pd.to_datetime(values).time() == datetime.strptime(str_time, '%H:%M:%S').time():
            break
        index = index + 1
    return index

def get_exit_data(stock_data, stock_data_remaining, entry_price, exit_data, transaction_type):
    target_index = -1
    stoploss_index = -1
    exit_price = 0
    pl_percentage = 0
    st_candle_index = -2

    if exit_data.stoploss == SL_SUPER_TREND_UP:
        st_candle_index, exit_data.stoploss = get_st_signal_change_candle_price(stock_data=stock_data_remaining,
                                                            direction='up',
                                                            period=exit_data.st_period,
                                                            multiplier=exit_data.st_multiplier)
    elif exit_data.stoploss == SL_SUPER_TREND_DOWN:
        st_candle_index, exit_data.stoploss = get_st_signal_change_candle_price(stock_data=stock_data_remaining,
                                                               direction='down',
                                                               period=exit_data.st_period,
                                                               multiplier=exit_data.st_multiplier)

    max_sl_price = get_stoploss_price_by_percentage(entry_price, exit_data.max_stoploss_perc, transaction_type)

    if transaction_type == "buy":
        exit_data.stoploss = max(exit_data.stoploss, max_sl_price)
        lst_index = stock_data_remaining[stock_data_remaining[HIGH_PRICE].gt(exit_data.target)].index
        if len(lst_index) > 0:
            target_index = lst_index[0]

        if st_candle_index < target_index or st_candle_index == -2:
            lst_index = stock_data_remaining[stock_data_remaining[LOW_PRICE].le(exit_data.stoploss)].index
            if len(lst_index) > 0:
                stoploss_index = lst_index[0]
        if st_candle_index == -1:
            stoploss_index = -1
    else:
        exit_data.stoploss = min(exit_data.stoploss, max_sl_price)
        lst_index = stock_data_remaining[stock_data_remaining[LOW_PRICE].le(exit_data.target)].index
        if len(lst_index) > 0:
            target_index = lst_index[0]

        if st_candle_index < target_index or st_candle_index == -2:
            lst_index = stock_data_remaining[stock_data_remaining[HIGH_PRICE].gt(exit_data.stoploss)].index
            if len(lst_index) > 0:
                stoploss_index = lst_index[0]
        if st_candle_index == -1:
            stoploss_index = -1

    #if target and stoploss is -1 then exit price is day close price
    if target_index == -1 and stoploss_index == -1:
        #get the close price index
        day_close_index = get_time_index_from_pd_column(stock_data[DATE_TIME], "15:05:00")
        exit_price = stock_data[CLOSE_PRICE].values[day_close_index]
    #if target index = -1 then exit price is stop loss price
    else:
        if target_index < 0 and stoploss_index > -1:
            exit_price = exit_data.stoploss
        # if stop index = -1 then exit price is target price
        elif stoploss_index < 0 and target_index > -1:
            exit_price = exit_data.target
        else:
            if target_index < stoploss_index:
                exit_price = exit_data.target
            else:
                exit_price = exit_data.stoploss

    #calculate profit percentage
    if exit_price > 0 and entry_price > 0:
        if transaction_type == "buy":
            pl_percentage = ((exit_price - entry_price)/exit_price) * 100
        else:
            pl_percentage = ((entry_price - exit_price)/entry_price) * 100
    return exit_price, pl_percentage

def get_target_price_by_percentage(price, percentage, transaction_type, buffer_percentage=0.1):
    target_price = 0.0
    buffer_percentage = (buffer_percentage / 100)
    if transaction_type == "buy":
        target_price = price + ((price * percentage)/100)
        target_price = target_price + (target_price * buffer_percentage)
    else:
        target_price = price - ((price * percentage)/100)
        target_price = target_price - (target_price * buffer_percentage)
    return round(target_price, 2)

def get_stoploss_price_by_percentage(price, percentage, transaction_type, buffer_percentage=0.1):
    exit_price = 0.0
    buffer_percentage = (buffer_percentage / 100)
    if transaction_type == "buy":
        exit_price = price - ((price * percentage)/100)
        exit_price = exit_price + (exit_price * buffer_percentage)
    else:
        exit_price = price + ((price * percentage)/100)
        exit_price = exit_price - (exit_price * buffer_percentage)
    return round(exit_price, 2)

def is_DaysHigher_stock(stock_data, period=3):
    is_higher_stock = True
    rsi = 0.0

    # latest rsi should be greater than 65
    current_avg_gain, current_avg_loss, rsi = compute_rsi(stock_data, 14)
    if rsi < 65 or stock_data[CLOSE_PRICE].values[0] < 50:
        is_higher_stock = False
    else:
        #high low close verification
        for index in range(period):
            if stock_data[HIGH_PRICE].values[index] <= stock_data[HIGH_PRICE].values[index + 1]:
                is_higher_stock = False
                break
            if stock_data[CLOSE_PRICE].values[index] <= stock_data[CLOSE_PRICE].values[index + 1]:
                is_higher_stock = False
                break
            if stock_data[LOW_PRICE].values[index] <= stock_data[LOW_PRICE].values[index + 1]:
                is_higher_stock = False
                break

        #validate RSI
        if is_higher_stock:
            avg_gain, avg_loss, last_period_rsi = compute_rsi(stock_data[0:len(stock_data) - period], 14)
            if last_period_rsi < 50:
                is_higher_stock = False
            else:
                #last 3 days RSI should be in ascending order
                for index in range(period):
                    current_avg_gain, current_avg_loss, current_rsi = \
                            compute_rsi(stock_data[index:stock_data.shape[0]], 14)
                    prev_avg_gain, prev_avg_loss, prev_rsi = \
                        compute_rsi(stock_data[(index+1):stock_data.shape[0]], 14)
                    if current_rsi < prev_rsi:
                        is_higher_stock = False
                        break
    return is_higher_stock, rsi

def is_DaysLower_stock(stock_data, period=3):
    is_lower_stock = True
    rsi = 0.0
    # latest close price should be greater than 50
    if stock_data[CLOSE_PRICE].values[0] < 50:
        is_lower_stock = False
    else:
        #high low close verification
        for index in range(period):
            if stock_data[HIGH_PRICE].values[index] >= stock_data[HIGH_PRICE].values[index + 1]:
                is_lower_stock = False
                break
            if stock_data[CLOSE_PRICE].values[index] >= stock_data[CLOSE_PRICE].values[index + 1]:
                is_lower_stock = False
                break
            if stock_data[LOW_PRICE].values[index] >= stock_data[LOW_PRICE].values[index + 1]:
                is_lower_stock = False
                break

        # latest rsi should be less than 35
        current_avg_gain, current_avg_loss, rsi = compute_rsi(stock_data, 14)
        if rsi > 35:
            is_lower_stock = False

        if is_lower_stock:
            #check for previous day hlc with last day hlc and rsi
            current_avg_gain, current_avg_loss, rsi = compute_rsi(stock_data[period:stock_data.shape[0]], 14)
            prev_avg_gain, prev_avg_loss, prev_rsi = \
                compute_rsi(stock_data[(period + 1):stock_data.shape[0]], 14)
            if stock_data[HIGH_PRICE].values[period] >= stock_data[HIGH_PRICE].values[period+1] or \
               stock_data[LOW_PRICE].values[period] >= stock_data[LOW_PRICE].values[period + 1] or \
               stock_data[CLOSE_PRICE].values[period] >= stock_data[CLOSE_PRICE].values[period + 1] or \
               rsi > prev_rsi:
               is_lower_stock = False

            #validate RSI
            avg_gain, avg_loss, last_period_rsi = compute_rsi(stock_data[0:len(stock_data) - period], 14)

            if last_period_rsi > 50:
                is_lower_stock = False
            else:
                #last 3 days RSI should be in ascending order
                for index in range(period):
                    current_avg_gain, current_avg_loss, rsi = \
                            compute_rsi(stock_data[index:stock_data.shape[0]], 14)
                    prev_avg_gain, prev_avg_loss, prev_rsi = \
                        compute_rsi(stock_data[(index+1):stock_data.shape[0]], 14)
                    if rsi > prev_rsi:
                        is_lower_stock = False
                        break

    return is_lower_stock, rsi

def is_open_equals_high(stock_data):
    b_is_open_equals_high = False
    if stock_data[OPEN_PRICE].values[0] == stock_data[HIGH_PRICE].values[0] and \
            stock_data[OPEN_PRICE].values[0].is_integer():
        b_is_open_equals_high = True
    return b_is_open_equals_high

def is_open_equals_low(stock_data):
    b_is_open_equals_low = False
    if stock_data[OPEN_PRICE].values[0] == stock_data[LOW_PRICE].values[0] and \
            stock_data[OPEN_PRICE].values[0].is_integer():
        b_is_open_equals_low = True
    return b_is_open_equals_low

def is_candle_doji(open, high, low, close,high_low_perc = 1.0):
    is_doji = False
    #print("abs: ", abs(open - close))
    #print("(close * (0.1/100)): ", (close * (0.1/100)))
    #print("(high - low): ", (high - low))
    #print("(close * (1/100): ", (close * (1/100)))
    if abs(open - close) < (close * (0.1/100)) and \
            (high - low) > (close * (high_low_perc/100)):
        is_doji = True
    return is_doji

def fetchCandleMultipleStocks(dict_historic_interval_candle_data, lst_stocks, str_from_date,
                              str_to_date, date_wise=False):
    dict_candle_data = {}
    str_from_date = str_from_date.split(" ")[0]
    str_to_date = str_to_date.split(" ")[0]
    str_end_date = datetime.strptime(str_to_date, "%Y-%m-%d") + timedelta(days=1)
    str_to_date = str_end_date.strftime("%Y-%m-%d")
    print("str_from_date: ", str_from_date)
    print("str_to_date: ", str_from_date)
    for stock in lst_stocks:
        if stock in dict_historic_interval_candle_data:
            stock_data = dict_historic_interval_candle_data[stock]
            index_filter = (stock_data[DATE_TIME] >= str_from_date) & (stock_data[DATE_TIME] <= str_to_date)
            dict_candle_data[stock] = stock_data.loc[index_filter].reset_index(drop=True)

    print("Utility - dict_candle_data", dict_candle_data)
    return dict_candle_data

def get_start_end_index_by_date_from_pd_column(date_time_column, str_from_date, str_to_date):
    start_index = -1
    end_index = -1
    index = 0
    for values in date_time_column.values:

        if start_index < 0:
            if pd.to_datetime(values).date() >= datetime.strptime(str_from_date, '%Y-%m-%d').date() and \
               pd.to_datetime(values).date() <= datetime.strptime(str_to_date, '%Y-%m-%d').date():
                start_index = index
        else:
            if pd.to_datetime(values).date() > datetime.strptime(str_to_date, '%Y-%m-%d').date():
                    end_index = index
                    break
        index = index + 1
    if end_index < 0:
        end_index = index
    return start_index, end_index

def get_nine_thirty_candle_index(interval):
    nine_thirty_candle_index = -1
    interval = interval.lower()
    if interval == "3minute":
        nine_thirty_candle_index = 4
    elif interval == "5minute":
        nine_thirty_candle_index = 2
    elif interval == "10minute":
        nine_thirty_candle_index = 1
    elif interval == "15minute":
        nine_thirty_candle_index = 0

    return nine_thirty_candle_index

def get_entry_price_index(entry_price, stock_data):
    entry_price_index = -1
    for index in range(len(stock_data)):
        if entry_price >= stock_data[LOW_PRICE].values[index] and \
            entry_price <= stock_data[HIGH_PRICE].values[index]:
            entry_price_index = index
            break
    return entry_price_index

def get_current_time(self):
    return time.strftime("%H:%M:%S", time.localtime())

def get_test_mode_start_end_time(self):
    return (datetime.now() + timedelta(minutes=1)).strftime("%H:%M:%S"), \
        (datetime.now() + timedelta(minutes=1)).strftime("%H:%M:%S"), \
        (datetime.now() + timedelta(minutes=4)).strftime("%H:%M:%S"), \
        (datetime.now() + timedelta(minutes=3)).strftime("%H:%M:%S")

def get_sleep_time_from_time(p_time):
    if (datetime.now().time() > p_time.time()):
        return int((datetime.now() - p_time).seconds)
    else:
        return int((p_time - datetime.now()).seconds)

def get_candle_time_series(p_interval, p_start_time="09:15:00", p_end_time="15:30:00"):
    lst_time_series = []
    str_start_time_object = datetime.strptime(p_start_time, '%H:%M:%S')
    str_stop_time_object = datetime.strptime(p_end_time, '%H:%M:%S')

    #update the first time interval
    l_current_time = (str_start_time_object).strftime("%H:%M:%S")
    str_start_time_object = datetime.strptime(l_current_time, '%H:%M:%S')
    lst_time_series.append(l_current_time)

    while(str_start_time_object.time() < str_stop_time_object.time()):
        l_current_time = (str_start_time_object + timedelta(minutes=p_interval)).strftime("%H:%M:%S")
        str_start_time_object = datetime.strptime(l_current_time, '%H:%M:%S')
        lst_time_series.append(l_current_time)
    return lst_time_series

def get_trailing_stop_loss_buy(p_entry_price, p_stop_loss_actual,
                               p_stop_loss_price_current, p_dayhigh, p_increment_value):
    l_stop_loss_price = p_stop_loss_price_current
    if not p_dayhigh == 0 and (p_dayhigh > p_entry_price) and p_increment_value > 0:
            l_temp_stop_loss_price = p_stop_loss_actual + (math.floor((p_dayhigh - p_entry_price) / p_increment_value) * p_increment_value)
            l_stop_loss_price = max(p_stop_loss_price_current, l_temp_stop_loss_price)
    return l_stop_loss_price

def get_option_price(p_reference_value, p_round_off_value, p_buffer, p_option_type):
    price_after_round_off = p_round_off_value * round(p_reference_value / p_round_off_value)
    option_price = (price_after_round_off + p_buffer) if p_option_type == "PE" else (price_after_round_off - p_buffer)
    return option_price

def get_option_chain_data(p_data_time, p_index_value, p_strike_value, p_option_chain, p_total_call_oi, p_total_put_oi):

    # get wall strike data
    l_option_chain_data = option_chain_data()
    l_option_chain_data.date_time = p_data_time

    #option wall data
    l_option_chain_data.call_wall_data.strike_price, l_option_chain_data.call_wall_data.oi, \
        l_option_chain_data.put_wall_data.strike_price, l_option_chain_data.put_wall_data.oi = calculate_wall_strike(p_option_chain)

    # calculate atm strike
    l_option_chain_data.atm_strike, l_option_chain_data.atm_straddle_price = calculate_atm_strike(p_index_value, p_strike_value, p_option_chain)

    #calculate greeks
    if "greeks" in p_option_chain.columns:
        pe_greeks, ce_greeks = calculate_greeks(l_option_chain_data.atm_strike, p_option_chain)
        l_option_chain_data.put_greeks.gamma = pe_greeks["gamma"]
        l_option_chain_data.put_greeks.delta = pe_greeks["delta"]
        l_option_chain_data.put_greeks.theta = pe_greeks["theta"]
        l_option_chain_data.put_greeks.vega = pe_greeks["vega"]
        l_option_chain_data.put_greeks.iv = pe_greeks["iv"]

        l_option_chain_data.call_greeks.gamma = ce_greeks["gamma"]
        l_option_chain_data.call_greeks.delta = ce_greeks["delta"]
        l_option_chain_data.call_greeks.theta = ce_greeks["theta"]
        l_option_chain_data.call_greeks.vega = ce_greeks["vega"]
        l_option_chain_data.call_greeks.iv = ce_greeks["iv"]

    #calculate pcr
    l_option_chain_data.pcr = calculate_pcr(p_total_call_oi, p_total_put_oi)

    #calculate max pain
    l_option_chain_data.max_pain = calculate_max_pain(p_option_chain)

    return l_option_chain_data


def calculate_wall_strike(p_option_chain):
    max_index = p_option_chain.loc[p_option_chain["option_type"] == "CE", "oi"].idxmax()
    call_wall_strike = p_option_chain.loc[max_index, "strike_price"]
    call_wall_oi = p_option_chain.loc[max_index, "oi"]
    max_index = p_option_chain.loc[p_option_chain["option_type"] == "PE", "oi"].idxmax()
    put_wall_strike = p_option_chain.loc[max_index, "strike_price"]
    put_wall_oi = p_option_chain.loc[max_index, "oi"]
    return call_wall_strike, call_wall_oi, put_wall_strike, put_wall_oi


def calculate_atm_strike(p_index_value, p_strike_value, p_option_chain):
    floor_index_value = (p_index_value // p_strike_value) * p_strike_value
    ceil_index_value = ((p_index_value + (p_strike_value - 1)) // p_strike_value) * p_strike_value

    #calculate floor strike diff
    floor_pe_idx = p_option_chain.index[
        (p_option_chain["strike_price"] == floor_index_value) & (p_option_chain["option_type"] == "PE")
        ]
    floor_ce_idx = p_option_chain.index[
        (p_option_chain["strike_price"] == floor_index_value) & (p_option_chain["option_type"] == "CE")
        ]


    floor_diff_value = abs(float(p_option_chain.loc[floor_ce_idx, "ltp"].iloc[0]) - float(p_option_chain.loc[floor_pe_idx, "ltp"].iloc[0]))

    #calculate ceil strike diff
    ceil_pe_idx = p_option_chain.index[
        (p_option_chain["strike_price"] == ceil_index_value) & (p_option_chain["option_type"] == "PE")
        ]
    ceil_ce_idx = p_option_chain.index[
        (p_option_chain["strike_price"] == ceil_index_value) & (p_option_chain["option_type"] == "CE")
        ]

    ceil_diff_value = abs(float(p_option_chain.loc[ceil_ce_idx, "ltp"].iloc[0]) - float(p_option_chain.loc[ceil_pe_idx, "ltp"].iloc[0]))

    if floor_diff_value <= ceil_diff_value:
        return floor_index_value, (float(p_option_chain.loc[floor_ce_idx, "ltp"].iloc[0] + float(p_option_chain.loc[floor_pe_idx, "ltp"].iloc[0])))
    else:
        return ceil_index_value, (float(p_option_chain.loc[ceil_ce_idx, "ltp"].iloc[0]) + float(p_option_chain.loc[ceil_pe_idx, "ltp"].iloc[0]))

def calculate_greeks(p_strike_price, p_option_chain):

    if "greeks" not in p_option_chain.columns:
        return 0.0, 0.0

    index = p_option_chain.index[
        (p_option_chain["strike_price"] == p_strike_price) & (p_option_chain["option_type"] == "PE")
        ]

    pe_greeks = p_option_chain.loc[index, "greeks"]


    index = p_option_chain.index[
        (p_option_chain["strike_price"] == p_strike_price) & (p_option_chain["option_type"] == "CE")
        ]
    ce_greeks = p_option_chain.loc[index, "greeks"]

    return pe_greeks.values[0], ce_greeks.values[0]


def calculate_pcr(p_total_call_oi, p_total_put_oi):
    return round((p_total_put_oi/p_total_call_oi), 2)


def calculate_max_pain(df):
        calls = df[df["option_type"] == "CE"]
        puts = df[df["option_type"] == "PE"]

        strikes = sorted(df["strike_price"].dropna().unique())

        pain_list = []

        for S in strikes:
            call_pain = ((S - calls["strike_price"]) * calls["oi"])
            call_pain = call_pain[calls["strike_price"] < S].sum()

            put_pain = ((puts["strike_price"] - S) * puts["oi"])
            put_pain = put_pain[puts["strike_price"] > S].sum()

            total_pain = call_pain + put_pain

            pain_list.append((S, total_pain))

        pain_df = pd.DataFrame(pain_list, columns=["strike", "pain"])

        max_pain_strike = pain_df.loc[pain_df["pain"].idxmin(), "strike"]

        return max_pain_strike

def to_python_type(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    elif isinstance(value, (np.floating,)):
        return float(value)
    return value

def get_previous_expirty_day(p_week_day_no, p_time_delta = 0):
    # Get today's date
    today = datetime.today() - timedelta(days=p_time_delta)

    # Find the most recent Tuesday§
    days_since_tuesday = (today.weekday() - 1) % 7
    last_tuesday = today - timedelta(days=days_since_tuesday)

    # Get previous Tuesday (one more week back)
    previous_to_previous_tuesday = last_tuesday - timedelta(weeks=1)

    return (previous_to_previous_tuesday + timedelta(days=1)).strftime("%Y-%m-%d"), last_tuesday.strftime("%Y-%m-%d")



