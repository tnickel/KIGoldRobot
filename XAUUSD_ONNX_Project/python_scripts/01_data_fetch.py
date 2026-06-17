#!/usr/bin/env python3
"""
Phase 1: Python Data Engineering (01_data_fetch.py)
--------------------------------------------------
This script connects to the MetaTrader 5 (MT5) terminal, downloads historical H1 data
for XAUUSD (Gold), performs robust feature engineering (including RSI, ATR-normalized EMA 
distances, and MACD), and constructs a classification target variable based on the next 
bar's close movement.

Features are normalized by ATR to make them scale-invariant across different price regimes.
"""

import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# Configuration Parameters & Timeframe Mapping
SYMBOL = "XAUUSD"
YEARS_OF_DATA = 5
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1
}

# Technical Indicator Parameters
RSI_PERIOD = 14
ATR_PERIOD = 14
EMA_FAST = 20
EMA_MEDIUM = 50
SMA_SLOW = 200

# Classification Target Parameter
# Threshold multiplier of ATR to determine a significant price move.
# Target = 1 if Close(t+1) - Close(t) > (ATR(t) * ATR_THRESHOLD_MULTIPLE)
# Target = -1 if Close(t+1) - Close(t) < -(ATR(t) * ATR_THRESHOLD_MULTIPLE)
# Target = 0 otherwise
ATR_THRESHOLD_MULTIPLE = 0.25

# Global variables initialized in main
TIMEFRAME = mt5.TIMEFRAME_M15
TIMEFRAME_STR = "M15"


def initialize_mt5():
    """Initializes connection to MT5 terminal."""
    print("Initializing MetaTrader 5...")
    if not mt5.initialize():
        print(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        sys.exit(1)
    
    # Verify terminal status and network connection
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        print("Failed to get terminal info.")
        mt5.shutdown()
        sys.exit(1)
        
    version_info = mt5.version()
    print(f"Connected to MT5: Version {version_info[0]}, Build {version_info[1]} ({version_info[2]})")
    
    # Ensure SYMBOL is visible in Market Watch
    if not mt5.symbol_select(SYMBOL, True):
        print(f"Failed to select symbol {SYMBOL}. Checking availability...")
        # Try to find symbol
        symbols = mt5.symbols_get()
        symbol_names = [s.name for s in symbols]
        matched_symbols = [s for s in symbol_names if SYMBOL in s]
        print(f"Available matching symbols in terminal: {matched_symbols}")
        mt5.shutdown()
        sys.exit(1)
        
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"Failed to get details for symbol {SYMBOL}")
        mt5.shutdown()
        sys.exit(1)
        
    print(f"Symbol {SYMBOL} selected. Digit resolution: {symbol_info.digits}, Point value: {symbol_info.point}")
    return symbol_info


def fetch_symbol_data(symbol, timeframe, utc_from, utc_to):
    """Helper to fetch rates for a symbol and convert to DataFrame."""
    print(f"Fetching data for {symbol}...")
    # Select symbol
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select symbol {symbol}")
        return None
    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(f"No rates found for {symbol}. Error: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df


def fetch_historical_data(years):
    """Fetches years of historical data from MT5 for XAUUSD, DXY, and VIX, then joins them."""
    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=years * 365)
    
    # 1. Fetch main XAUUSD data
    df_xau = fetch_symbol_data(SYMBOL, TIMEFRAME, utc_from, utc_to)
    if df_xau is None:
        print("Failed to fetch primary symbol data.")
        mt5.shutdown()
        sys.exit(1)
    print(f"Successfully fetched {len(df_xau)} candles for {SYMBOL}.")

    # 2. Fetch DXY data
    df_dxy = fetch_symbol_data("DXY", TIMEFRAME, utc_from, utc_to)
    if df_dxy is not None:
        # Calculate DXY EMA20 and DXY ATR14 on its own series
        dxy_close = df_dxy['close']
        dxy_high = df_dxy['high']
        dxy_low = df_dxy['low']
        
        # Calculate DXY ATR 14
        dxy_hl = dxy_high - dxy_low
        dxy_hc = (dxy_high - dxy_close.shift(1)).abs()
        dxy_lc = (dxy_low - dxy_close.shift(1)).abs()
        dxy_tr = pd.concat([dxy_hl, dxy_hc, dxy_lc], axis=1).max(axis=1)
        dxy_atr = dxy_tr.ewm(alpha=1/14, adjust=False).mean()
        
        # Calculate DXY EMA20
        dxy_ema20 = dxy_close.ewm(span=20, adjust=False).mean()
        
        # Distance normalized
        df_dxy['dxy_dist_ema20'] = (dxy_close - dxy_ema20) / (dxy_atr + 1e-10)
        
        # Merge into df_xau
        df_xau = df_xau.join(df_dxy[['dxy_dist_ema20']], how='left')
        df_xau['dxy_dist_ema20'] = df_xau['dxy_dist_ema20'].ffill().bfill()
        print("Merged DXY features.")
    else:
        print("Warning: DXY data not available. Using 0 values.")
        df_xau['dxy_dist_ema20'] = 0.0

    # 3. Fetch VIX data
    df_vix = fetch_symbol_data("VIX", TIMEFRAME, utc_from, utc_to)
    if df_vix is not None:
        df_xau = df_xau.join(df_vix[['close']].rename(columns={'close': 'vix_close'}), how='left')
        df_xau['vix_close'] = df_xau['vix_close'].ffill().bfill()
        print("Merged VIX features.")
    else:
        print("Warning: VIX data not available. Using 0 values.")
        df_xau['vix_close'] = 0.0

    return df_xau


def engineer_features(df):
    """
    Computes technical indicators and normalizes price distances by ATR 
    to ensure scale-invariance across the 5-year period.
    """
    print("Engineering features...")
    features = pd.DataFrame(index=df.index)
    
    # Keep baseline price info for target calculation, but we will exclude raw prices from features
    close = df['close']
    high = df['high']
    low = df['low']
    open_p = df['open']
    
    # 1. Volatility (ATR)
    # TR (True Range) calculation
    high_low = high - low
    high_close_prev = (high - close.shift(1)).abs()
    low_close_prev = (low - close.shift(1)).abs()
    
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/ATR_PERIOD, adjust=False).mean()
    features['atr'] = atr
    
    # 2. RSI (Wilder's smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10) # avoid division by zero
    features['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. Moving Average Distances (Normalized by ATR)
    ema20 = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema50 = close.ewm(span=EMA_MEDIUM, adjust=False).mean()
    sma200 = close.rolling(window=SMA_SLOW).mean()
    
    features['dist_ema20'] = (close - ema20) / (atr + 1e-10)
    features['dist_ema50'] = (close - ema50) / (atr + 1e-10)
    features['dist_sma200'] = (close - sma200) / (atr + 1e-10)
    
    # 4. MACD (Normalized by ATR)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    features['macd_diff_norm'] = (macd_line - signal_line) / (atr + 1e-10)
    
    # 5. Price Action Features (Relative to ATR)
    features['body_size_norm'] = (close - open_p) / (atr + 1e-10)
    features['upper_shadow_norm'] = (high - np.maximum(close, open_p)) / (atr + 1e-10)
    features['lower_shadow_norm'] = (np.minimum(close, open_p) - low) / (atr + 1e-10)
    
    # 6. Volume Normalization (Relative to 20-period rolling average) - FIX: Use tick_volume
    rolling_volume = df['tick_volume'].rolling(window=20).mean()
    features['tick_volume_ratio'] = df['tick_volume'] / (rolling_volume + 1e-10)
    
    # 7. External Market Regimes
    features['dxy_dist_ema20'] = df['dxy_dist_ema20']
    features['vix_close'] = df['vix_close']
    
    # 8. Session & Cyclical Time Features
    hours = df.index.hour
    days = df.index.dayofweek
    features['sin_hour'] = np.sin(2 * np.pi * hours / 24.0)
    features['cos_hour'] = np.cos(2 * np.pi * hours / 24.0)
    features['sin_day'] = np.sin(2 * np.pi * days / 7.0)
    features['cos_day'] = np.cos(2 * np.pi * days / 7.0)
    
    # 9. Classification Target Construction
    # Target is defined by the price action of the next bar (t+1)
    next_close = close.shift(-1)
    future_diff = next_close - close
    
    # Dynamic Volatility-Based Threshold
    threshold = atr * ATR_THRESHOLD_MULTIPLE
    
    # Target classes:
    # 1  -> Price goes up by more than threshold
    # -1 -> Price goes down by more than threshold
    # 0  -> Price stays flat within threshold limits
    features['target'] = np.where(
        future_diff > threshold, 1, 
        np.where(future_diff < -threshold, -1, 0)
    )
    
    # Add raw Close price to features temporarily for debug visualization (we will drop it or not train on it)
    features['raw_close'] = close
    features['future_diff'] = future_diff
    features['dynamic_threshold'] = threshold
    
    # Drop rows with NaN (the first SMA_SLOW rows have NaNs due to rolling 200, and last row has NaN for target)
    cleaned_features = features.dropna()
    
    return cleaned_features



def main():
    global TIMEFRAME, TIMEFRAME_STR, YEARS_OF_DATA
    
    parser = argparse.ArgumentParser(description="Fetch historical data from MT5 and engineer features.")
    parser.add_argument("--timeframe", type=str, default="M15", help="Timeframe (e.g. M15, M30, H1)")
    parser.add_argument("--years", type=int, default=5, help="Number of years of data to fetch")
    args = parser.parse_args()
    
    if args.timeframe not in TIMEFRAME_MAP:
        print(f"Error: Unsupported timeframe {args.timeframe}. Choose from: {list(TIMEFRAME_MAP.keys())}")
        sys.exit(1)
        
    TIMEFRAME_STR = args.timeframe
    TIMEFRAME = TIMEFRAME_MAP[TIMEFRAME_STR]
    YEARS_OF_DATA = args.years
    
    # Setup directories
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Initialize connection
    symbol_info = initialize_mt5()
    
    try:
        # Fetch OHLCV
        df = fetch_historical_data(YEARS_OF_DATA)
        
        # Engineer features & targets
        features_df = engineer_features(df)
        
        # Split into training features and target analysis
        print("\nDataset Summary:")
        print(f"Total processed samples: {len(features_df)}")
        print(f"Feature columns: {list(features_df.columns[:-4])}")
        
        # Calculate Class Distribution
        class_counts = features_df['target'].value_counts()
        print("\nTarget Class Distribution:")
        for cls, count in class_counts.items():
            percentage = (count / len(features_df)) * 100
            label = "BUY (1)" if cls == 1 else ("SELL (-1)" if cls == -1 else "HOLD (0)")
            print(f"  {label:10s}: {count:6d} ({percentage:.2f}%)")
            
        # Save to file
        output_path = os.path.join(DATA_DIR, "xauusd_features.csv")
        features_df.to_csv(output_path)
        print(f"\nSaved engineered dataset to: {output_path}")
        
    finally:
        # Ensure MT5 is shut down properly
        print("Shutting down MetaTrader 5 connection...")
        mt5.shutdown()


if __name__ == "__main__":
    main()
