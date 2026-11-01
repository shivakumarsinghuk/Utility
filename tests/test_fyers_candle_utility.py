# -*- coding: utf-8 -*-
"""Pure unit tests for FYERS tick-to-five-minute candle aggregation."""

import unittest

import pandas as pd

from DataTypes.defines import (CANDLE_TYPE, CLOSE_PRICE, DATE_TIME, HIGH_PRICE,
                               LOW_PRICE, OPEN_PRICE, VOLUME_DATA)
from Utility.fyers_candle_utility import (FIVE_MINUTE_CANDLE_COLUMNS,
                                          FyersCandleUtility)


def epoch_ist(hour, minute, second=0):
    timestamp = pd.Timestamp(f"2026-10-27 {hour:02d}:{minute:02d}:{second:02d}",
                             tz="Asia/Kolkata")
    return int(timestamp.timestamp())


class FyersCandleUtilityTests(unittest.TestCase):
    def setUp(self):
        self.utility = FyersCandleUtility()

    def test_aggregates_ticks_across_five_minute_boundary_and_matches_schema(self):
        ticks = pd.DataFrame([
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 15, 10),
             "ltp": 100, "vol_traded_today": 100},
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 19, 59),
             "ltp": 101, "vol_traded_today": 104},
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 20),
             "ltp": 103, "vol_traded_today": 110},
            {"symbol": "NSE:SBIN-EQ", "last_traded_time": epoch_ist(9, 22),
             "ltp": 102, "vol_traded_today": 112},
        ])

        result = self.utility.build_5min_candles(
            ticks, ["NSE:SBIN-EQ", "NSE:EMPTY-EQ"])
        candles = result["NSE:SBIN-EQ"]

        self.assertEqual(list(candles.columns), FIVE_MINUTE_CANDLE_COLUMNS)
        self.assertEqual(list(candles[DATE_TIME]), [
            pd.Timestamp("2026-10-27 09:15:00"),
            pd.Timestamp("2026-10-27 09:20:00"),
        ])
        self.assertEqual(candles[[OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE]].values.tolist(),
                         [[100.0, 101.0, 100.0, 101.0],
                          [103.0, 103.0, 102.0, 102.0]])
        self.assertEqual(candles[VOLUME_DATA].tolist(), [4, 8])
        self.assertEqual(candles[CANDLE_TYPE].tolist(), ["GREEN", "RED"])
        self.assertIsInstance(candles.index, pd.RangeIndex)
        self.assertEqual(str(candles[DATE_TIME].dtype), "datetime64[ns]")
        self.assertEqual(str(candles[OPEN_PRICE].dtype), "float64")
        self.assertEqual(str(candles[VOLUME_DATA].dtype), "int64")
        self.assertEqual(str(candles[CANDLE_TYPE].dtype), "object")
        self.assertIsNone(candles[DATE_TIME].dt.tz)
        self.assertEqual(list(candles[DATE_TIME]), sorted(candles[DATE_TIME]))
        self.assertEqual(list(result["NSE:EMPTY-EQ"].columns), FIVE_MINUTE_CANDLE_COLUMNS)
        self.assertTrue(result["NSE:EMPTY-EQ"].empty)

    def test_out_of_order_duplicate_and_missing_volume_ticks(self):
        first = {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 15),
                 "ltp": 10, "vol_traded_today": 500}
        second = {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 16),
                  "ltp": 12, "vol_traded_today": 503}
        ticks = pd.DataFrame([
            first,
            second,
            second.copy(),
            {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 15, 30),
             "ltp": 11, "vol_traded_today": 504},
            {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 17),
             "ltp": 9},
        ])

        candle = self.utility.build_5min_candles(ticks)["NSE:TEST-EQ"].iloc[0]

        self.assertEqual(candle[OPEN_PRICE], 10.0)
        self.assertEqual(candle[HIGH_PRICE], 12.0)
        self.assertEqual(candle[LOW_PRICE], 9.0)
        self.assertEqual(candle[CLOSE_PRICE], 9.0)
        self.assertEqual(candle[VOLUME_DATA], 4)
        self.assertEqual(candle[CANDLE_TYPE], "RED")

    def test_partial_candle_is_returned_and_empty_input_has_schema(self):
        ticks = pd.DataFrame([
            {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 18),
             "ltp": 20, "vol_traded_today": 1},
        ])
        result = self.utility.build_5min_candles(ticks, ["NSE:TEST-EQ", "NSE:NO-TICKS-EQ"])

        self.assertEqual(len(result["NSE:TEST-EQ"]), 1)
        self.assertEqual(result["NSE:TEST-EQ"].iloc[0][DATE_TIME],
                         pd.Timestamp("2026-10-27 09:15:00"))
        self.assertEqual(result["NSE:TEST-EQ"].iloc[0][VOLUME_DATA], 0)
        self.assertEqual(list(result["NSE:NO-TICKS-EQ"].columns), FIVE_MINUTE_CANDLE_COLUMNS)
        self.assertEqual(list(result["NSE:NO-TICKS-EQ"].dtypes.astype(str)),
                         ["datetime64[ns]", "float64", "float64", "float64",
                          "float64", "int64", "object"])

    def test_ticks_outside_nse_session_are_ignored(self):
        ticks = pd.DataFrame([
            {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(9, 14, 59), "ltp": 1},
            {"symbol": "NSE:TEST-EQ", "last_traded_time": epoch_ist(15, 30), "ltp": 2},
        ])

        candles = self.utility.build_5min_candles(ticks, ["NSE:TEST-EQ"])["NSE:TEST-EQ"]

        self.assertTrue(candles.empty)
        self.assertEqual(list(candles.columns), FIVE_MINUTE_CANDLE_COLUMNS)


if __name__ == "__main__":
    unittest.main()
