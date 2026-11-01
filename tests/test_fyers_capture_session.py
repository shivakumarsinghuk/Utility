# -*- coding: utf-8 -*-
"""Unit tests for the live capture runner's CSV export helpers."""

from pathlib import Path
import tempfile
import unittest

import pandas as pd

from Utility.tests.capture_fyers_websocket_session import (
    _candle_frame_by_symbol,
    _write_csv,
)


class FyersCaptureSessionTests(unittest.TestCase):
    def test_candle_export_keeps_symbol_and_expected_columns(self):
        candles = pd.DataFrame([{
            "date": pd.Timestamp("2026-10-30 09:15:00"),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 12,
            "candle_type": "GREEN",
        }])

        result = _candle_frame_by_symbol({"NSE:SBIN-EQ": candles})

        self.assertEqual(list(result.columns), [
            "symbol", "date", "open", "high", "low", "close", "volume", "candle_type"
        ])
        self.assertEqual(result.loc[0, "symbol"], "NSE:SBIN-EQ")
        self.assertEqual(result.loc[0, "date"], pd.Timestamp("2026-10-30 09:15:00"))

    def test_csv_checkpoint_is_readable_and_temp_file_is_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "session" / "ticks.csv"
            expected = pd.DataFrame([{"symbol": "NSE:SBIN-EQ", "ltp": 100.5}])

            _write_csv(expected, output_path)

            pd.testing.assert_frame_equal(pd.read_csv(output_path), expected)
            self.assertFalse(output_path.with_name(output_path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
