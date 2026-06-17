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
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# Configuration Parameters
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_H1
YEARS_OF_DATA = 5
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

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
ATR_THRESHOLD_MULTIPLE = 0.5


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


def fetch_historical_data(years):
    """Fetches years of historical H1 data from MT5 for SYMBOL."""
    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=years * 365)
    
    print(f"Fetching data for {SYMBOL} from {utc_from.strftime('%Y-%m-%d')} to {utc_to.strftime('%Y-%m-%d')}...")
    
    rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME, utc_from, utc_to)
    
    if rates is None or len(rates) == 0:
        print(f"Failed to fetch data. Error: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
        
    df = pd.DataFrame(rates)
    # Convert time in seconds to datetime
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    print(f"Successfully fetched {len(df)} candles.")
    return df


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
    # Normalizing by ATR ensures that standard deviations / distance thresholds scale 
    # appropriately with volatility regimes instead of absolute dollar differences.
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
    
    # 6. Volume Normalization (Relative to 20-period rolling average)
    rolling_volume = df['real_volume'].rolling(window=20).mean()
    features['volume_ratio'] = df['real_volume'] / (rolling_volume + 1e-10)
    
    # 7. Classification Target Construction
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
        output_path = os.path.join(DATA_DIR, "xauusd_h1_features.csv")
        features_df.to_csv(output_path)
        print(f"\nSaved engineered dataset to: {output_path}")
        
    finally:
        # Ensure MT5 is shut down properly
        print("Shutting down MetaTrader 5 connection...")
        mt5.shutdown()


if __name__ == "__main__":
    main()
