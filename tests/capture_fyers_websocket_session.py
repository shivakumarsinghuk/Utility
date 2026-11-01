# -*- coding: utf-8 -*-
"""Capture live FYERS ticks and five-minute candles to CSV files.

Run from the Executor_One repository root. This is a live-session smoke test,
not a substitute for the fake-SDK and synthetic-tick unit tests. It follows
the existing FYERS YAML login flow and writes ignored CSV artifacts under Logs.

Unit tests (no credentials or market session required)::

    python -m unittest \
        BrokerUtility.broker_platform.fyers.test.test_fyers_data_websocket \
        Utility.tests.test_fyers_candle_utility \
        Utility.tests.test_quotes_utility_fyers \
        Utility.tests.test_fyers_capture_session

Live capture (starts immediately, defaults to stopping at 15:35 IST)::

    python -m Utility.tests.capture_fyers_websocket_session \
        --config /path/to/fyers_config.yml --symbol NSE:SBIN-EQ
"""

import argparse
from datetime import datetime, time as datetime_time
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from BrokerUtility.broker_platform.fyers.fyers_utility import fyers_utitlity
from Utility.fyers_candle_utility import FyersCandleUtility


IST = ZoneInfo("Asia/Kolkata")
RAW_TICK_COLUMNS_WHEN_EMPTY = [
    "symbol", "ltp", "last_traded_time", "vol_traded_today", "received_at"
]


def _parse_end_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as error:
        raise argparse.ArgumentTypeError("end time must use HH:MM, in IST") from error


def _write_csv(frame, output_path):
    """Replace a CSV atomically so periodic checkpoints remain readable."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the destination and rename only after serialization finishes,
    # so an interrupted checkpoint does not leave a truncated CSV in place.
    temp_path = output_path.with_name(output_path.name + ".tmp")
    frame.to_csv(temp_path, index=False)
    os.replace(temp_path, output_path)


def _candle_frame_by_symbol(candles_by_symbol):
    """Combine the utility's per-symbol candle frames into one export table."""
    frames = []
    for symbol, candles in candles_by_symbol.items():
        frame = candles.copy()
        frame.insert(0, "symbol", symbol)
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=[
            "symbol", "date", "open", "high", "low", "close", "volume", "candle_type"
        ])
    return pd.concat(frames, ignore_index=True)


def _read_credentials(config_path, parser):
    """Load the project's existing FYERS YAML keys without logging secrets."""
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    required_keys = ("user_name", "client_id", "secret_id", "pin", "totp", "phone_no")
    missing = [key for key in required_keys if not config.get(key)]
    if missing:
        parser.error(f"missing {', '.join(missing)} in {config_path}")
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Capture FYERS WebSocket ticks and derived five-minute candles to CSV"
    )
    parser.add_argument("--config", required=True, type=Path,
                        help="YAML file with the existing FYERS credential keys")
    parser.add_argument("--symbol", required=True, action="append",
                        help="Full FYERS symbol, repeat for multiple symbols, e.g. NSE:SBIN-EQ")
    parser.add_argument("--end-time", type=_parse_end_time, default=datetime_time(15, 35),
                        help="Stop time in IST (default: 15:35)")
    parser.add_argument("--checkpoint-seconds", type=float, default=60,
                        help="How often to refresh the raw-tick CSV during the run (default: 60)")
    parser.add_argument("--candle-checkpoint-seconds", type=float, default=300,
                        help="How often to refresh the candle CSV (default: 300)")
    parser.add_argument("--output-dir", type=Path, default=Path("Logs/fyers_websocket_session"),
                        help="CSV output directory (default: Logs/fyers_websocket_session)")
    args = parser.parse_args()

    if args.checkpoint_seconds <= 0:
        parser.error("--checkpoint-seconds must be greater than zero")
    if args.candle_checkpoint_seconds <= 0:
        parser.error("--candle-checkpoint-seconds must be greater than zero")

    symbols = list(dict.fromkeys(args.symbol))
    config = _read_credentials(args.config, parser)
    broker = fyers_utitlity(
        user_name=config["user_name"],
        client_id=config["client_id"],
        secret_id=config["secret_id"],
        pin=config["pin"],
        totp=config["totp"],
        phone_no=config["phone_no"],
    )
    if not broker.get_running_status():
        raise SystemExit("Fyers login failed; see the output above")

    websocket = broker.get_data_websocket()
    started_at = datetime.now(IST)
    started_monotonic = time.monotonic()
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tick_path = args.output_dir / f"fyers_ticks_{run_id}.csv"
    candle_path = args.output_dir / f"fyers_5min_candles_{run_id}.csv"

    print(f"Subscribing to: {', '.join(symbols)}")
    print(f"Raw tick CSV: {tick_path}")
    print(f"Candle CSV:   {candle_path}")
    print(f"Capturing until {args.end_time.strftime('%H:%M')} IST; press Ctrl+C to stop early.")
    print("Checkpoint cadence: raw ticks every "
          f"{args.checkpoint_seconds:g}s; candles every "
          f"{args.candle_checkpoint_seconds:g}s")

    ticks = pd.DataFrame(columns=RAW_TICK_COLUMNS_WHEN_EMPTY)
    last_candle_checkpoint = 0.0
    candle_utility = FyersCandleUtility()
    try:
        # Subscription begins immediately. The loop stays active until the
        # selected IST end time; FYERS sends ticks when the market/feed opens.
        websocket.subscribe(symbols)
        while True:
            now = datetime.now(IST)
            end_at = datetime.combine(now.date(), args.end_time, tzinfo=now.tzinfo)
            if now >= end_at:
                break

            wait_seconds = min(args.checkpoint_seconds, (end_at - now).total_seconds())
            time.sleep(max(wait_seconds, 0))
            ticks = websocket.get_tick_data()
            if ticks.empty:
                ticks = pd.DataFrame(columns=RAW_TICK_COLUMNS_WHEN_EMPTY)
                print(f"{datetime.now(IST):%H:%M:%S} IST: waiting for ticks")
            else:
                print(f"{datetime.now(IST):%H:%M:%S} IST: {len(ticks)} tick rows captured")
            # Keep a recoverable raw snapshot even if the process is stopped
            # before the end-of-session cleanup runs.
            _write_csv(ticks, tick_path)

            elapsed = time.monotonic() - started_monotonic
            # Write the first candle snapshot with the first raw checkpoint,
            # then refresh it at the configured cadence (including the open bar).
            if (last_candle_checkpoint == 0.0
                    or elapsed - last_candle_checkpoint >= args.candle_checkpoint_seconds):
                candles = candle_utility.build_5min_candles(ticks, symbols)
                _write_csv(_candle_frame_by_symbol(candles), candle_path)
                last_candle_checkpoint = elapsed
    except KeyboardInterrupt:
        print("Capture interrupted; saving the ticks received so far.")
    finally:
        # Closing first lets the SDK finish its callback thread before the final snapshot.
        websocket.close()
        ticks = websocket.get_tick_data()
        if ticks.empty:
            ticks = pd.DataFrame(columns=RAW_TICK_COLUMNS_WHEN_EMPTY)
        _write_csv(ticks, tick_path)

        candles = candle_utility.build_5min_candles(ticks, symbols)
        candle_frame = _candle_frame_by_symbol(candles)
        _write_csv(candle_frame, candle_path)

    print(f"Saved {len(ticks)} raw tick rows to {tick_path}")
    print(f"Saved {len(candle_frame)} five-minute candles to {candle_path}")


if __name__ == "__main__":
    main()
