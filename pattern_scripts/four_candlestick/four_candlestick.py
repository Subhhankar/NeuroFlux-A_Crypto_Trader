import pandas as pd
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
MAX_PATTERNS = 50
MARUBOZU_SHADOW_THRESHOLD = 0.1  # For Concealing Baby Swallow
MARUBOZU_BODY_FACTOR = 0.8      # For Concealing Baby Swallow

# === Trend Determination with Caching ===
def determine_trends(df, idx, cache=None):
    if cache is None:
        cache = {}
    if idx in cache:
        return cache[idx]

    trends = {'short_term': 'neutral', 'long_term': 'neutral'}

    if idx >= SHORT_TERM_PERIOD:
        short_change = (df.iloc[idx]['close'] - df.iloc[idx - SHORT_TERM_PERIOD]['close']) / df.iloc[idx - SHORT_TERM_PERIOD]['close']
        trends['short_term'] = 'up' if short_change > 0 else 'down'

    if idx >= LONG_TERM_PERIOD:
        long_change = (df.iloc[idx]['close'] - df.iloc[idx - LONG_TERM_PERIOD]['close']) / df.iloc[idx - LONG_TERM_PERIOD]['close']
        trends['long_term'] = 'up' if long_change > 0 else 'down'

    cache[idx] = trends
    return trends

# === Helper Functions ===
def is_bearish(candle):
    return candle['close'] < candle['open']

def is_bullish(candle):
    return candle['close'] > candle['open']

def is_marubozu(candle, avg_size):
    body = abs(candle['close'] - candle['open'])
    shadows = abs(candle['high'] - max(candle['close'], candle['open'])) + abs(min(candle['close'], candle['open']) - candle['low'])
    return is_bearish(candle) and shadows < MARUBOZU_SHADOW_THRESHOLD * body and body > MARUBOZU_BODY_FACTOR * avg_size

def engulfing(c_big, c_small):
    return c_big['high'] >= c_small['high'] and c_big['low'] <= c_small['low']

# === Consolidated Pattern Detection ===
def detect_four_candlestick_patterns(df):
    patterns = []
    trend_cache = {}
    avg_candle_size = (df['high'] - df['low']).rolling(10).mean()

    print("Scanning for all four-candlestick patterns...")
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 4, len(df))):
        t4 = df.iloc[i - 4]  # t-4
        t3 = df.iloc[i - 3]  # t-3
        t2 = df.iloc[i - 2]  # t-2
        t1 = df.iloc[i - 1]  # t-1
        trends = determine_trends(df, i - 1, trend_cache)

        # Count patterns to enforce limits
        pattern_counts = {
            'concealing_baby_swallow': 0,
            'bullish_three_line_strike': 0,
            'bearish_three_line_strike': 0
        }
        for pattern in patterns:
            pattern_counts[pattern['pattern']] = pattern_counts.get(pattern['pattern'], 0) + 1

        if all(count >= MAX_PATTERNS for count in pattern_counts.values()):
            break

        # === Concealing Baby Swallow ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            is_marubozu(t4, avg_candle_size[i - 4]) and
            is_marubozu(t3, avg_candle_size[i - 3]) and t3['open'] < t4['close'] and
            t2['open'] < t3['close'] and t2['high'] > t3['open'] and is_bearish(t2) and
            engulfing(t1, t2) and is_bearish(t1) and
            pattern_counts.get('concealing_baby_swallow', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'concealing_baby_swallow',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

        # === Bullish Three Line Strike ===
        if (
            is_bullish(t4) and is_bullish(t3) and is_bullish(t2) and
            t3['close'] > t4['close'] and t2['close'] > t3['close'] and
            t1['open'] > t2['close'] and t1['close'] < t4['open'] and is_bearish(t1) and
            pattern_counts.get('bullish_three_line_strike', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_three_line_strike',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

        # === Bearish Three Line Strike ===
        if (
            is_bearish(t4) and is_bearish(t3) and is_bearish(t2) and
            t3['close'] < t4['close'] and t2['close'] < t3['close'] and
            t1['open'] < t2['close'] and t1['close'] > t4['open'] and is_bullish(t1) and
            pattern_counts.get('bearish_three_line_strike', 0) < MAX_PATTERNS
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_three_line_strike',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': t1['close']
            })

    return patterns

# === Main Analysis Function ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_four_candlestick_patterns(df)

    # Count patterns by type
    pattern_counts = {}
    for pattern in patterns:
        ptype = pattern['pattern']
        pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1

    print("\nPattern Detection Summary:")
    for ptype, count in pattern_counts.items():
        print(f"{ptype.replace('_', ' ').title()}: {count}")

    return patterns

if __name__ == "__main__":
    patterns = run_analysis("OHCLV.csv")