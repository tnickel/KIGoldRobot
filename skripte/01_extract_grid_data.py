import os
import sys
import datetime
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# Configuration
SYMBOL = "AUDUSD"
START_DATE = datetime.datetime(2021, 6, 1, tzinfo=datetime.timezone.utc)
END_DATE = datetime.datetime(2026, 6, 15, tzinfo=datetime.timezone.utc)
POINT = 0.00001  # 5 decimals

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calc_adx(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)
    
    plus_dm = np.where((high - prev_high) > (prev_low - low), plus_dm, 0.0)
    minus_dm = np.where((prev_low - low) > (high - prev_high), minus_dm, 0.0)
    
    tr_smoothed = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (tr_smoothed + 1e-10)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (tr_smoothed + 1e-10)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx

def calc_er(series, period=10):
    direction = (series - series.shift(period)).abs()
    volatility = series.diff().abs().rolling(window=period).sum()
    er = direction / (volatility + 1e-10)
    return er

def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_stochastic(df, period_k=14, period_d=3):
    low_min = df['low'].rolling(window=period_k).min()
    high_max = df['high'].rolling(window=period_k).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min + 1e-10)
    d = k.rolling(window=period_d).mean()
    return k, d

def calc_cci(df, period=14):
    tp = (df['high'] + df['low'] + df['close']) / 3
    sma = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma) / (0.015 * mad + 1e-10)
    return cci

def get_rates(symbol, timeframe, start, end):
    print(f"Fetching rates for {symbol} on {timeframe}...", flush=True)
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is None or len(rates) == 0:
        print(f"Error: Could not fetch rates for {symbol} on {timeframe}. Error code: {mt5.last_error()}", flush=True)
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    return df

def main():
    if not mt5.initialize():
        print("MetaTrader5 initialization failed!", flush=True)
        sys.exit(1)
        
    print(f"MT5 initialized. Fetching historical data for {SYMBOL}...")
    
    # Timeframe mapping
    tf_m5 = mt5.TIMEFRAME_M5
    tf_m15 = mt5.TIMEFRAME_M15
    tf_h1 = mt5.TIMEFRAME_H1
    tf_h4 = mt5.TIMEFRAME_H4
    
    tf_d1 = mt5.TIMEFRAME_D1
    df_m5 = get_rates(SYMBOL, tf_m5, START_DATE, END_DATE)
    df_m15 = get_rates(SYMBOL, tf_m15, START_DATE, END_DATE)
    df_h1 = get_rates(SYMBOL, tf_h1, START_DATE, END_DATE)
    df_h4 = get_rates(SYMBOL, tf_h4, START_DATE, END_DATE)
    df_d1 = get_rates(SYMBOL, tf_d1, START_DATE, END_DATE)
    df_vix_m5 = get_rates("VIX", tf_m5, START_DATE, END_DATE)
    df_us500_h1 = get_rates("US500", tf_h1, START_DATE, END_DATE)
    df_xauusd_h1 = get_rates("XAUUSD", tf_h1, START_DATE, END_DATE)
    df_dxy_m5 = get_rates("DXY", tf_m5, START_DATE, END_DATE)
    df_dxy_h1 = get_rates("DXY", tf_h1, START_DATE, END_DATE)
    df_audjpy_h1 = get_rates("AUDJPY", tf_h1, START_DATE, END_DATE)
    df_euraud_h1 = get_rates("EURAUD", tf_h1, START_DATE, END_DATE)
    df_gbpaud_h1 = get_rates("GBPAUD", tf_h1, START_DATE, END_DATE)
    df_usdjpy_h1 = get_rates("USDJPY", tf_h1, START_DATE, END_DATE)
    
    mt5.shutdown()
    
    if (df_m5 is None or df_m15 is None or df_h1 is None or df_h4 is None or df_d1 is None or
        df_vix_m5 is None or df_us500_h1 is None or df_xauusd_h1 is None or
        df_dxy_m5 is None or df_dxy_h1 is None or df_audjpy_h1 is None or
        df_euraud_h1 is None or df_gbpaud_h1 is None or df_usdjpy_h1 is None):
        print("Data extraction failed. Exiting.")
        sys.exit(1)
        
    print(f"Data fetched successfully. M5 bars: {len(df_m5)}, M15: {len(df_m15)}, H1: {len(df_h1)}, H4: {len(df_h4)}")
    print(f"Macro symbols fetched. VIX M5: {len(df_vix_m5)}, US500 H1: {len(df_us500_h1)}, XAUUSD H1: {len(df_xauusd_h1)}")
    
    # Calculate indicators
    print("Calculating indicators...")
    
    # Macro indicators
    df_us500_h1['rsi_us500_h1'] = calc_rsi(df_us500_h1['close'], period=14)
    df_xauusd_h1['rsi_xauusd_h1'] = calc_rsi(df_xauusd_h1['close'], period=14)
    df_dxy_h1['rsi_dxy_h1'] = calc_rsi(df_dxy_h1['close'], period=14)
    df_audjpy_h1['rsi_audjpy_h1'] = calc_rsi(df_audjpy_h1['close'], period=14)
    df_euraud_h1['rsi_euraud_h1'] = calc_rsi(df_euraud_h1['close'], period=14)
    df_gbpaud_h1['rsi_gbpaud_h1'] = calc_rsi(df_gbpaud_h1['close'], period=14)
    df_usdjpy_h1['rsi_usdjpy_h1'] = calc_rsi(df_usdjpy_h1['close'], period=14)
    
    # H4: Trend EMA 250
    df_h4['ema250_h4'] = df_h4['close'].ewm(span=250, adjust=False).mean()
    
    # M15: RSI 21, ATR 10, Stochastic
    df_m15['rsi_m15'] = calc_rsi(df_m15['close'], period=21)
    df_m15['atr_m15'] = calc_atr(df_m15, period=10)
    df_m15['atr_avg_m15'] = df_m15['atr_m15'].rolling(window=30).mean()
    df_m15['atr_ratio_m15'] = df_m15['atr_m15'] / (df_m15['atr_avg_m15'] + 1e-10)
    df_m15['stoch_k_m15'], df_m15['stoch_d_m15'] = calc_stochastic(df_m15, period_k=14, period_d=3)
    
    # H1: RSI 14, ADX 14, ER 10, ATR 14, Envelopes, MACD, CCI, EMAs
    df_h1['rsi_h1'] = calc_rsi(df_h1['close'], period=14)
    df_h1['adx_h1'] = calc_adx(df_h1, period=14)
    df_h1['er_h1'] = calc_er(df_h1['close'], period=10)
    df_h1['atr_h1'] = calc_atr(df_h1, period=14)
    df_h1['atr_avg_h1'] = df_h1['atr_h1'].rolling(window=30).mean()
    df_h1['atr_ratio_h1'] = df_h1['atr_h1'] / (df_h1['atr_avg_h1'] + 1e-10)
    df_h1['macd_line_h1'], df_h1['macd_sig_h1'], df_h1['macd_hist_h1'] = calc_macd(df_h1['close'], fast=12, slow=26, signal=9)
    df_h1['cci_h1'] = calc_cci(df_h1, period=14)
    df_h1['ema50_h1'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    df_h1['ema200_h1'] = df_h1['close'].ewm(span=200, adjust=False).mean()
    df_h1['ema50_ema200_dist_h1'] = (df_h1['ema50_h1'] - df_h1['ema200_h1']) / POINT
    
    # Envelopes
    ema14_close_h1 = df_h1['close'].ewm(span=14, adjust=False).mean()
    df_h1['env_up_h1'] = ema14_close_h1 * (1 + 0.133 / 100)
    ema20_low_h1 = df_h1['low'].ewm(span=20, adjust=False).mean()
    df_h1['env_down_h1'] = ema20_low_h1 * (1 - 0.299 / 100)
    
    # M5: RSI 14
    df_m5['rsi_m5'] = calc_rsi(df_m5['close'], period=14)
    
    # Daily RSI 14
    df_d1['rsi_d1'] = calc_rsi(df_d1['close'], period=14)
    
    # H4 RSI 14
    df_h4['rsi_h4'] = calc_rsi(df_h4['close'], period=14)
    
    # H1 SMA 200 and distance
    df_h1['sma200_h1'] = df_h1['close'].rolling(window=200).mean()
    df_h1['dist_sma200_h1'] = (df_h1['close'] - df_h1['sma200_h1']) / POINT
    
    # H4 SMA 200 and distance
    df_h4['sma200_h4'] = df_h4['close'].rolling(window=200).mean()
    df_h4['dist_sma200_h4'] = (df_h4['close'] - df_h4['sma200_h4']) / POINT
    
    # H1 Bollinger Bands (20, 2)
    sma_bb_h1 = df_h1['close'].rolling(window=20).mean()
    std_bb_h1 = df_h1['close'].rolling(window=20).std(ddof=0)
    df_h1['bb_upper_h1'] = sma_bb_h1 + 2 * std_bb_h1
    df_h1['bb_lower_h1'] = sma_bb_h1 - 2 * std_bb_h1
    df_h1['bb_width_h1'] = (df_h1['bb_upper_h1'] - df_h1['bb_lower_h1']) / (sma_bb_h1 + 1e-10)
    df_h1['dist_bb_upper_h1'] = (df_h1['close'] - df_h1['bb_upper_h1']) / POINT
    df_h1['dist_bb_lower_h1'] = (df_h1['close'] - df_h1['bb_lower_h1']) / POINT
    
    # H4 Bollinger Bands (20, 2)
    sma_bb_h4 = df_h4['close'].rolling(window=20).mean()
    std_bb_h4 = df_h4['close'].rolling(window=20).std(ddof=0)
    df_h4['bb_upper_h4'] = sma_bb_h4 + 2 * std_bb_h4
    df_h4['bb_lower_h4'] = sma_bb_h4 - 2 * std_bb_h4
    df_h4['bb_width_h4'] = (df_h4['bb_upper_h4'] - df_h4['bb_lower_h4']) / (sma_bb_h4 + 1e-10)
    df_h4['dist_bb_upper_h4'] = (df_h4['close'] - df_h4['bb_upper_h4']) / POINT
    df_h4['dist_bb_lower_h4'] = (df_h4['close'] - df_h4['bb_lower_h4']) / POINT
    
    # M5 Volume Ratio
    df_m5['vol_ratio_m5'] = df_m5['tick_volume'] / (df_m5['tick_volume'].rolling(window=20).mean() + 1e-10)
    df_m5['vol_ratio_m5_shift1'] = df_m5['vol_ratio_m5'].shift(1)
    
    # M5 Consecutive Bars
    closes = df_m5['close'].values
    opens = df_m5['open'].values
    n = len(df_m5)
    consec = np.zeros(n, dtype=np.float32)
    state = 0
    current_count = 0
    for i in range(n):
        c = closes[i]
        o = opens[i]
        if c > o:
            if state == 1:
                current_count += 1
            else:
                state = 1
                current_count = 1
            consec[i] = current_count
        elif c < o:
            if state == -1:
                current_count += 1
            else:
                state = -1
                current_count = 1
            consec[i] = -current_count
        else:
            state = 0
            current_count = 0
            consec[i] = 0
    df_m5['consec_bars_m5'] = consec
    df_m5['consec_bars_m5_shift1'] = df_m5['consec_bars_m5'].shift(1)
    
    # Shift indicators to match shift 1 (completed bar values)
    print("Shifting indicators for shift 1...")
    df_h4['ema250_h4_shift1'] = df_h4['ema250_h4'].shift(1)
    df_h4['rsi_h4_shift1'] = df_h4['rsi_h4'].shift(1)
    df_h4['dist_sma200_h4_shift1'] = df_h4['dist_sma200_h4'].shift(1)
    df_h4['bb_width_h4_shift1'] = df_h4['bb_width_h4'].shift(1)
    df_h4['dist_bb_upper_h4_shift1'] = df_h4['dist_bb_upper_h4'].shift(1)
    df_h4['dist_bb_lower_h4_shift1'] = df_h4['dist_bb_lower_h4'].shift(1)
    
    df_d1['rsi_d1_shift1'] = df_d1['rsi_d1'].shift(1)
    
    df_h1['dist_sma200_h1_shift1'] = df_h1['dist_sma200_h1'].shift(1)
    df_h1['bb_width_h1_shift1'] = df_h1['bb_width_h1'].shift(1)
    df_h1['dist_bb_upper_h1_shift1'] = df_h1['dist_bb_upper_h1'].shift(1)
    df_h1['dist_bb_lower_h1_shift1'] = df_h1['dist_bb_lower_h1'].shift(1)
    
    df_m15['rsi_m15_shift1'] = df_m15['rsi_m15'].shift(1)
    df_m15['atr_ratio_m15_shift1'] = df_m15['atr_ratio_m15'].shift(1)
    df_m15['stoch_k_m15_shift1'] = df_m15['stoch_k_m15'].shift(1)
    df_m15['stoch_d_m15_shift1'] = df_m15['stoch_d_m15'].shift(1)
    
    df_h1['rsi_h1_shift1'] = df_h1['rsi_h1'].shift(1)
    df_h1['adx_h1_shift1'] = df_h1['adx_h1'].shift(1)
    df_h1['er_h1_shift1'] = df_h1['er_h1'].shift(1)
    df_h1['atr_ratio_h1_shift1'] = df_h1['atr_ratio_h1'].shift(1)
    df_h1['env_up_h1_shift1'] = df_h1['env_up_h1'].shift(1)
    df_h1['env_down_h1_shift1'] = df_h1['env_down_h1'].shift(1)
    df_h1['macd_line_h1_shift1'] = df_h1['macd_line_h1'].shift(1)
    df_h1['macd_sig_h1_shift1'] = df_h1['macd_sig_h1'].shift(1)
    df_h1['macd_hist_h1_shift1'] = df_h1['macd_hist_h1'].shift(1)
    df_h1['cci_h1_shift1'] = df_h1['cci_h1'].shift(1)
    df_h1['ema50_ema200_dist_h1_shift1'] = df_h1['ema50_ema200_dist_h1'].shift(1)
    
    df_m5['rsi_m5_shift1'] = df_m5['rsi_m5'].shift(1)
    df_m5['close_shift1'] = df_m5['close'].shift(1)
    df_m5['spread_shift1'] = df_m5['spread'].shift(1)
    
    df_vix_m5['vix_close_shift1'] = df_vix_m5['close'].shift(1)
    df_us500_h1['rsi_us500_h1_shift1'] = df_us500_h1['rsi_us500_h1'].shift(1)
    df_xauusd_h1['rsi_xauusd_h1_shift1'] = df_xauusd_h1['rsi_xauusd_h1'].shift(1)
    df_dxy_m5['dxy_close_shift1'] = df_dxy_m5['close'].shift(1)
    df_dxy_h1['rsi_dxy_h1_shift1'] = df_dxy_h1['rsi_dxy_h1'].shift(1)
    df_audjpy_h1['rsi_audjpy_h1_shift1'] = df_audjpy_h1['rsi_audjpy_h1'].shift(1)
    df_euraud_h1['rsi_euraud_h1_shift1'] = df_euraud_h1['rsi_euraud_h1'].shift(1)
    df_gbpaud_h1['rsi_gbpaud_h1_shift1'] = df_gbpaud_h1['rsi_gbpaud_h1'].shift(1)
    df_usdjpy_h1['rsi_usdjpy_h1_shift1'] = df_usdjpy_h1['rsi_usdjpy_h1'].shift(1)
    
    # Align indicators to M5 using pd.merge_asof
    print("Aligning indicators to M5 candles...")
    df_m5 = df_m5.sort_index()
    df_m15 = df_m15.sort_index()
    df_h1 = df_h1.sort_index()
    df_h4 = df_h4.sort_index()
    df_d1 = df_d1.sort_index()
    df_vix_m5 = df_vix_m5.sort_index()
    df_us500_h1 = df_us500_h1.sort_index()
    df_xauusd_h1 = df_xauusd_h1.sort_index()
    df_dxy_m5 = df_dxy_m5.sort_index()
    df_dxy_h1 = df_dxy_h1.sort_index()
    df_audjpy_h1 = df_audjpy_h1.sort_index()
    df_euraud_h1 = df_euraud_h1.sort_index()
    df_gbpaud_h1 = df_gbpaud_h1.sort_index()
    df_usdjpy_h1 = df_usdjpy_h1.sort_index()
    
    df = pd.merge_asof(
        df_m5, 
        df_m15[['rsi_m15_shift1', 'atr_ratio_m15_shift1', 'stoch_k_m15_shift1', 'stoch_d_m15_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_h1[['rsi_h1_shift1', 'adx_h1_shift1', 'er_h1_shift1', 'atr_ratio_h1_shift1', 'env_up_h1_shift1', 'env_down_h1_shift1',
                'macd_line_h1_shift1', 'macd_sig_h1_shift1', 'macd_hist_h1_shift1', 'cci_h1_shift1', 'ema50_ema200_dist_h1_shift1',
                'dist_sma200_h1_shift1', 'bb_width_h1_shift1', 'dist_bb_upper_h1_shift1', 'dist_bb_lower_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_h4[['ema250_h4_shift1', 'rsi_h4_shift1', 'dist_sma200_h4_shift1', 'bb_width_h4_shift1', 'dist_bb_upper_h4_shift1', 'dist_bb_lower_h4_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df,
        df_d1[['rsi_d1_shift1']],
        left_index=True,
        right_index=True,
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_vix_m5[['vix_close_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_us500_h1[['rsi_us500_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_xauusd_h1[['rsi_xauusd_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_dxy_m5[['dxy_close_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_dxy_h1[['rsi_dxy_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_audjpy_h1[['rsi_audjpy_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_euraud_h1[['rsi_euraud_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_gbpaud_h1[['rsi_gbpaud_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    df = pd.merge_asof(
        df, 
        df_usdjpy_h1[['rsi_usdjpy_h1_shift1']], 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    print("Calculating economic calendar news features...")
    csv_path = r"C:\Forex\Mt5\TickmillLifeMql5\MQL5\Files\calendar_export.csv"
    if not os.path.exists(csv_path):
        print(f"Error: Economic calendar export not found at {csv_path}!")
        sys.exit(1)
        
    df_news = pd.read_csv(csv_path, encoding='ansi')
    df_news['time'] = pd.to_datetime(df_news['time'], format='%Y.%m.%d %H:%M:%S').dt.tz_localize('UTC')
    df_news = df_news.sort_values('time')

    usd_news_times = df_news[df_news['currency'] == 'USD']['time'].tolist()
    aud_news_times = df_news[df_news['currency'] == 'AUD']['time'].tolist()

    import bisect
    
    def calc_minutes_to_next(time_series, news_times):
        res = []
        for t in time_series:
            idx = bisect.bisect_left(news_times, t)
            if idx < len(news_times):
                diff = (news_times[idx] - t).total_seconds() / 60.0
                res.append(min(diff, 1440.0))
            else:
                res.append(1440.0)
        return res

    df['minutes_to_usd_news'] = calc_minutes_to_next(df.index, usd_news_times)
    df['minutes_to_aud_news'] = calc_minutes_to_next(df.index, aud_news_times)

    # Drop rows with NaN in features
    features_to_check = [
        'ema250_h4_shift1', 'rsi_m15_shift1', 'atr_ratio_m15_shift1', 'stoch_k_m15_shift1', 'stoch_d_m15_shift1',
        'rsi_h1_shift1', 'adx_h1_shift1', 'er_h1_shift1', 'atr_ratio_h1_shift1', 
        'env_up_h1_shift1', 'env_down_h1_shift1', 'rsi_m5_shift1',
        'macd_line_h1_shift1', 'macd_sig_h1_shift1', 'macd_hist_h1_shift1', 'cci_h1_shift1', 'ema50_ema200_dist_h1_shift1',
        'vix_close_shift1', 'rsi_us500_h1_shift1', 'rsi_xauusd_h1_shift1',
        'dxy_close_shift1', 'rsi_dxy_h1_shift1', 'rsi_audjpy_h1_shift1', 'rsi_euraud_h1_shift1', 'rsi_gbpaud_h1_shift1', 'rsi_usdjpy_h1_shift1',
        'minutes_to_usd_news', 'minutes_to_aud_news', 'vol_ratio_m5_shift1', 'consec_bars_m5_shift1',
        'rsi_h4_shift1', 'rsi_d1_shift1', 'dist_sma200_h1_shift1', 'dist_sma200_h4_shift1', 'bb_width_h1_shift1', 'bb_width_h4_shift1',
        'dist_bb_upper_h1_shift1', 'dist_bb_lower_h1_shift1', 'dist_bb_upper_h4_shift1', 'dist_bb_lower_h4_shift1'
    ]
    df.dropna(subset=features_to_check, inplace=True)
    print(f"Aligned dataset size: {len(df)}")
    
    # Find breakthrough signals
    buy_signals = df[df['close_shift1'] < df['env_down_h1_shift1']].copy()
    buy_signals['is_buy'] = 1.0
    
    sell_signals = df[df['close_shift1'] > df['env_up_h1_shift1']].copy()
    sell_signals['is_buy'] = 0.0
    
    signals = pd.concat([buy_signals, sell_signals]).sort_index()
    print(f"Total potential breakthroughs: {len(signals)} (Buy: {len(buy_signals)}, Sell: {len(sell_signals)})")
    
    # Setup for fast grid simulation
    m5_times = df.index
    m5_opens = df['open'].values
    m5_highs = df['high'].values
    m5_lows = df['low'].values
    m5_closes = df['close'].values
    m5_spreads = df['spread'].values
    
    time_to_idx = {timeval: idx for idx, timeval in enumerate(m5_times)}
    
    tp_base = 50
    step_1 = 1000
    step_2 = 1330
    step_3 = 1768
    dd_limit = 300
    time_limit_bars = 120
    
    lots = [1.0, 1.38, 1.38 * 1.38]
    
    labels = []
    skipped_count = 0
    
    print("Simulating grid outcomes for all triggers...")
    
    for sig_time, row in signals.iterrows():
        sig_idx = time_to_idx.get(sig_time)
        if sig_idx is None or sig_idx + time_limit_bars >= len(m5_times):
            skipped_count += 1
            labels.append(np.nan)
            continue
            
        is_buy = row['is_buy'] == 1.0
        open_price = m5_opens[sig_idx]
        spread_val = m5_spreads[sig_idx]
        
        # Grid state
        orders = []  # list of tuples (entry_price, lot)
        
        if is_buy:
            entry_1 = open_price + spread_val * POINT
            orders.append((entry_1, lots[0]))
            drawdown_price = entry_1 - dd_limit * POINT
            
            label = 0
            
            for j in range(sig_idx, sig_idx + time_limit_bars):
                low_j = m5_lows[j]
                high_j = m5_highs[j]
                
                # Check TP
                total_vol = sum(o[1] for o in orders)
                avg_price = sum(o[0] * o[1] for o in orders) / total_vol
                tp_pts = max(tp_base - (len(orders) - 1) * 10, 30)
                basket_tp = avg_price + tp_pts * POINT
                
                if high_j >= basket_tp:
                    if len(orders) <= 2:
                        label = 1
                    else:
                        label = 0
                    break
                    
                # Check Drawdown limit
                if low_j < drawdown_price:
                    label = 0
                    break
                    
                # Check grid additions
                if len(orders) == 1:
                    target_price = entry_1 - step_1 * POINT
                    if low_j <= target_price:
                        orders.append((target_price, lots[1]))
                elif len(orders) == 2:
                    target_price = orders[1][0] - step_2 * POINT
                    if low_j <= target_price:
                        orders.append((target_price, lots[2]))
                elif len(orders) == 3:
                    target_price = orders[2][0] - step_3 * POINT
                    if low_j <= target_price:
                        label = 0
                        break
            labels.append(label)
            
        else:  # Sell
            entry_1 = open_price
            orders.append((entry_1, lots[0]))
            drawdown_price = entry_1 + dd_limit * POINT
            
            label = 0
            
            for j in range(sig_idx, sig_idx + time_limit_bars):
                low_j = m5_lows[j]
                high_j = m5_highs[j]
                
                # Check TP
                total_vol = sum(o[1] for o in orders)
                avg_price = sum(o[0] * o[1] for o in orders) / total_vol
                tp_pts = max(tp_base - (len(orders) - 1) * 10, 30)
                basket_tp = avg_price - tp_pts * POINT
                
                if low_j <= basket_tp:
                    if len(orders) <= 2:
                        label = 1
                    else:
                        label = 0
                    break
                    
                # Check Drawdown limit
                if high_j > drawdown_price:
                    label = 0
                    break
                    
                # Check grid additions
                if len(orders) == 1:
                    target_price = entry_1 + step_1 * POINT
                    if high_j >= target_price:
                        orders.append((target_price, lots[1]))
                elif len(orders) == 2:
                    target_price = orders[1][0] + step_2 * POINT
                    if high_j >= target_price:
                        orders.append((target_price, lots[2]))
                elif len(orders) == 3:
                    target_price = orders[2][0] + step_3 * POINT
                    if high_j >= target_price:
                        label = 0
                        break
            labels.append(label)
            
    signals['target'] = labels
    signals.dropna(subset=['target'], inplace=True)
    signals['target'] = signals['target'].astype(int)
    
    print(f"Simulation completed. Skipped due to boundary: {skipped_count}")
    print(f"Final labeled triggers: {len(signals)}")
    print(f"Class distribution: \n{signals['target'].value_counts()}")
    
    # Feature construction
    output_df = pd.DataFrame(index=signals.index)
    output_df['is_buy'] = signals['is_buy']
    output_df['dist_ema250_h4'] = (signals['close_shift1'] - signals['ema250_h4_shift1']) / POINT
    output_df['rsi_m5'] = signals['rsi_m5_shift1']
    output_df['rsi_m15'] = signals['rsi_m15_shift1']
    output_df['rsi_h1'] = signals['rsi_h1_shift1']
    output_df['adx_h1'] = signals['adx_h1_shift1']
    output_df['efficiency_ratio_h1'] = signals['er_h1_shift1']
    output_df['atr_ratio_m15'] = signals['atr_ratio_m15_shift1']
    output_df['atr_ratio_h1'] = signals['atr_ratio_h1_shift1']
    output_df['spread_points'] = signals['spread_shift1']
    
    dt_index = pd.to_datetime(signals.index)
    hour = dt_index.hour
    day_of_week = (dt_index.weekday + 1) % 7
    
    output_df['sin_hour'] = np.sin(2 * np.pi * hour / 24)
    output_df['cos_hour'] = np.cos(2 * np.pi * hour / 24)
    output_df['sin_day'] = np.sin(2 * np.pi * day_of_week / 7)
    output_df['cos_day'] = np.cos(2 * np.pi * day_of_week / 7)
    
    output_df['dist_env_up'] = (signals['close_shift1'] - signals['env_up_h1_shift1']) / POINT
    output_df['dist_env_down'] = (signals['close_shift1'] - signals['env_down_h1_shift1']) / POINT
    
    # 7 new features
    output_df['macd_h1'] = signals['macd_line_h1_shift1']
    output_df['macd_sig_h1'] = signals['macd_sig_h1_shift1']
    output_df['macd_hist_h1'] = signals['macd_hist_h1_shift1']
    output_df['stoch_k_m15'] = signals['stoch_k_m15_shift1']
    output_df['stoch_d_m15'] = signals['stoch_d_m15_shift1']
    output_df['cci_h1'] = signals['cci_h1_shift1']
    output_df['ema50_ema200_dist_h1'] = signals['ema50_ema200_dist_h1_shift1']
    
    # 3 new macro features
    output_df['vix_close'] = signals['vix_close_shift1']
    output_df['rsi_us500_h1'] = signals['rsi_us500_h1_shift1']
    output_df['rsi_xauusd_h1'] = signals['rsi_xauusd_h1_shift1']
    
    # 8 new macro, sentiment & news features
    output_df['minutes_to_usd_news'] = signals['minutes_to_usd_news']
    output_df['minutes_to_aud_news'] = signals['minutes_to_aud_news']
    output_df['dxy_close'] = signals['dxy_close_shift1']
    output_df['rsi_dxy_h1'] = signals['rsi_dxy_h1_shift1']
    output_df['rsi_audjpy_h1'] = signals['rsi_audjpy_h1_shift1']
    output_df['rsi_euraud_h1'] = signals['rsi_euraud_h1_shift1']
    output_df['rsi_gbpaud_h1'] = signals['rsi_gbpaud_h1_shift1']
    output_df['rsi_usdjpy_h1'] = signals['rsi_usdjpy_h1_shift1']
    
    # 5 new session, consecutive bars & volume ratio features
    output_df['is_asian_session'] = ((hour >= 22) | (hour < 8)).astype(float)
    output_df['is_london_session'] = ((hour >= 8) & (hour < 16)).astype(float)
    output_df['is_ny_session'] = ((hour >= 13) & (hour < 21)).astype(float)
    output_df['consec_bars_m5'] = signals['consec_bars_m5_shift1']
    output_df['vol_ratio_m5'] = signals['vol_ratio_m5_shift1']
    
    # 10 new Bollinger Bands, SMA-Distanzen, H4/D1 RSI features
    output_df['rsi_h4'] = signals['rsi_h4_shift1']
    output_df['rsi_d1'] = signals['rsi_d1_shift1']
    output_df['dist_sma200_h1'] = signals['dist_sma200_h1_shift1']
    output_df['dist_sma200_h4'] = signals['dist_sma200_h4_shift1']
    output_df['bb_width_h1'] = signals['bb_width_h1_shift1']
    output_df['bb_width_h4'] = signals['bb_width_h4_shift1']
    output_df['dist_bb_upper_h1'] = signals['dist_bb_upper_h1_shift1']
    output_df['dist_bb_lower_h1'] = signals['dist_bb_lower_h1_shift1']
    output_df['dist_bb_upper_h4'] = signals['dist_bb_upper_h4_shift1']
    output_df['dist_bb_lower_h4'] = signals['dist_bb_lower_h4_shift1']
    
    output_df['target'] = signals['target']
    
    assert not output_df.isnull().any().any(), "Output DataFrame contains NaN values!"
    
    # Resolve ToTheMoonKI data path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(repo_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    csv_path = os.path.join(data_dir, "grid_entries.csv")
    output_df.to_csv(csv_path)
    print(f"Successfully saved {len(output_df)} samples to {csv_path}")

if __name__ == "__main__":
    main()
