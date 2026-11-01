# -*- coding: utf-8 -*-
"""Build five-minute FYERS candles from full-mode data socket updates."""

from datetime import time as datetime_time
from numbers import Real
from zoneinfo import ZoneInfo

import pandas as pd

from DataTypes.defines import (CANDLE_TYPE, CLOSE_PRICE, DATE_TIME, HIGH_PRICE,
                               LOW_PRICE, OPEN_PRICE, VOLUME_DATA)

IST = ZoneInfo("Asia/Kolkata")
NSE_SESSION_START = datetime_time(9, 15)
NSE_SESSION_END = datetime_time(15, 30)
FIVE_MINUTE_INTERVAL = 5
FIVE_MINUTE_CANDLE_COLUMNS = [DATE_TIME, OPEN_PRICE, HIGH_PRICE, LOW_PRICE,
                              CLOSE_PRICE, VOLUME_DATA, CANDLE_TYPE]


def _empty_candle_data():
    """Return an empty frame with the same schema as populated candle data."""
    return pd.DataFrame({
        DATE_TIME: pd.Series(dtype="datetime64[ns]"),
        OPEN_PRICE: pd.Series(dtype="float64"),
        HIGH_PRICE: pd.Series(dtype="float64"),
        LOW_PRICE: pd.Series(dtype="float64"),
        CLOSE_PRICE: pd.Series(dtype="float64"),
        VOLUME_DATA: pd.Series(dtype="int64"),
        CANDLE_TYPE: pd.Series(dtype="object"),
    })


def _to_ist_naive_timestamp(value):
    """Convert an FYERS epoch or datetime value to a timezone-naive IST value.

    FYERS event times are epoch seconds. Datetime-like fallbacks are accepted
    for stored CSV data and tests; naive values are interpreted as IST.
    """
    if value is None or pd.isna(value):
        return pd.NaT

    if isinstance(value, Real) and not isinstance(value, bool):
        timestamp = pd.to_datetime(value, unit="s", utc=True)
    elif isinstance(value, str) and value.strip().isdigit():
        timestamp = pd.to_datetime(int(value.strip()), unit="s", utc=True)
    else:
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            return pd.NaT
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(IST)

    return timestamp.tz_convert(IST).tz_localize(None)


class FyersCandleUtility:
    """Aggregate FYERS ticks into NSE-session five-minute candles.

    ``p_df_ticks`` is the raw frame returned by the data WebSocket accessor. Its
    rows remain in callback-arrival order, which is used to calculate deltas
    from FYERS' cumulative ``vol_traded_today`` field before timestamps are
    sorted for OHLC aggregation.
    """

    @staticmethod
    def _candle_type(open_price, close_price):
        if open_price > close_price:
            return "RED"
        if open_price < close_price:
            return "GREEN"
        return "notknown"

    @staticmethod
    def _tick_timestamp(row):
        # Prefer exchange event time, then feed time; local receipt time is the
        # fallback for payloads that omit both exchange timestamps.
        for column in ("last_traded_time", "exch_feed_time", "received_at"):
            if column in row.index and pd.notna(row[column]):
                timestamp = _to_ist_naive_timestamp(row[column])
                if pd.notna(timestamp):
                    return timestamp
        return pd.NaT

    def build_5min_candles(self, p_df_ticks: pd.DataFrame,
                           p_symbols=None) -> dict[str, pd.DataFrame]:
        """Return ``{FYERS symbol: candle DataFrame}`` for the supplied ticks.

        Requested symbols with no valid ticks are returned with an empty frame
        carrying the full candle schema. Missing time or LTP messages cannot
        form OHLC candles and are ignored. The NSE session window is 09:15
        inclusive through 15:30 exclusive, in IST.

        Volume is a delta from FYERS' cumulative day volume. The first event for
        each symbol/day establishes a baseline; repeated or decreasing values
        add no volume. Exact duplicate callbacks remain in the raw tick store,
        but are excluded from candle calculations.
        """
        if p_symbols is None:
            requested_symbols = []
        elif isinstance(p_symbols, str):
            requested_symbols = [p_symbols]
        else:
            requested_symbols = list(dict.fromkeys(p_symbols))

        if p_df_ticks is None or p_df_ticks.empty or "symbol" not in p_df_ticks.columns:
            return {symbol: _empty_candle_data() for symbol in requested_symbols}

        ticks = p_df_ticks.copy().reset_index(drop=True)
        ticks["_receive_order"] = range(len(ticks))
        ticks["_timestamp"] = ticks.apply(self._tick_timestamp, axis=1)
        ticks["ltp"] = pd.to_numeric(ticks.get("ltp"), errors="coerce")
        ticks = ticks.dropna(subset=["symbol", "_timestamp", "ltp"])

        symbols_in_ticks = list(dict.fromkeys(ticks["symbol"].astype(str).tolist()))
        all_symbols = list(dict.fromkeys(requested_symbols + symbols_in_ticks))
        if ticks.empty:
            return {symbol: _empty_candle_data() for symbol in all_symbols}

        # Drop duplicate market events for candle math only. The WebSocket's
        # raw tick accessor intentionally retains every callback.
        duplicate_columns = ["symbol", "_timestamp", "ltp"]
        for column in ("vol_traded_today", "last_traded_qty"):
            if column in ticks.columns:
                duplicate_columns.append(column)
        ticks = ticks.drop_duplicates(subset=duplicate_columns, keep="first").copy()

        session_time = ticks["_timestamp"].dt.time
        ticks = ticks.loc[
            (session_time >= NSE_SESSION_START)
            & (session_time < NSE_SESSION_END)
        ].copy()
        if ticks.empty:
            return {symbol: _empty_candle_data() for symbol in all_symbols}

        # FYERS reports cumulative day volume. Count only positive changes;
        # the first observed value establishes the baseline and contributes 0.
        ticks["_volume_delta"] = 0
        if "vol_traded_today" in ticks.columns:
            high_water_by_symbol_day = {}
            arrival_rows = ticks.sort_values("_receive_order", kind="mergesort")
            for row_index, row in arrival_rows.iterrows():
                cumulative_volume = pd.to_numeric(row["vol_traded_today"], errors="coerce")
                if pd.isna(cumulative_volume):
                    continue
                cumulative_volume = int(cumulative_volume)
                symbol_day = (str(row["symbol"]), row["_timestamp"].date())
                previous_volume = high_water_by_symbol_day.get(symbol_day)
                if previous_volume is None:
                    high_water_by_symbol_day[symbol_day] = cumulative_volume
                elif cumulative_volume > previous_volume:
                    ticks.at[row_index, "_volume_delta"] = cumulative_volume - previous_volume
                    high_water_by_symbol_day[symbol_day] = cumulative_volume

        # Bars start at the NSE 09:15 open rather than midnight; stable sorting
        # below preserves callback order for equal-time open/close selection.
        session_open = ticks["_timestamp"].dt.normalize() + pd.Timedelta(
            hours=NSE_SESSION_START.hour, minutes=NSE_SESSION_START.minute
        )
        minutes_from_open = (ticks["_timestamp"] - session_open).dt.total_seconds() // 60
        bucket_minutes = (minutes_from_open // FIVE_MINUTE_INTERVAL) * FIVE_MINUTE_INTERVAL
        ticks["_bucket"] = session_open + pd.to_timedelta(bucket_minutes, unit="m")
        ticks = ticks.sort_values(["symbol", "_timestamp", "_receive_order"], kind="mergesort")

        candle_data = {}
        for symbol in all_symbols:
            symbol_ticks = ticks.loc[ticks["symbol"].astype(str) == symbol]
            if symbol_ticks.empty:
                candle_data[symbol] = _empty_candle_data()
                continue

            rows = []
            for candle_start, candle_ticks in symbol_ticks.groupby("_bucket", sort=True):
                open_price = float(candle_ticks.iloc[0]["ltp"])
                close_price = float(candle_ticks.iloc[-1]["ltp"])
                rows.append({
                    DATE_TIME: candle_start,
                    OPEN_PRICE: open_price,
                    HIGH_PRICE: float(candle_ticks["ltp"].max()),
                    LOW_PRICE: float(candle_ticks["ltp"].min()),
                    CLOSE_PRICE: close_price,
                    VOLUME_DATA: int(candle_ticks["_volume_delta"].sum()),
                    CANDLE_TYPE: self._candle_type(open_price, close_price),
                })

            frame = pd.DataFrame(rows, columns=FIVE_MINUTE_CANDLE_COLUMNS)
            frame[DATE_TIME] = pd.to_datetime(frame[DATE_TIME]).astype("datetime64[ns]")
            for column in (OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE):
                frame[column] = frame[column].astype(float)
            frame[VOLUME_DATA] = frame[VOLUME_DATA].astype("int64")
            frame[CANDLE_TYPE] = frame[CANDLE_TYPE].astype(object)
            candle_data[symbol] = frame.sort_values(DATE_TIME, kind="mergesort").reset_index(drop=True)

        return candle_data
