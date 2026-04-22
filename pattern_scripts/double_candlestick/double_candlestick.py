import pandas as pd
import numpy as np
from tqdm import tqdm

# === Configuration ===
SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
PRICE_TOLERANCE_ENGULFING = 0.0015  # 0.15% for engulfing and kicking
PRICE_TOLERANCE_MATCHING = 0.001   # 0.1% for matching patterns
OPEN_TOLERANCE_SEPARATING = 0.1    # For separating lines
MIN_BODY_RATIO_PIERCING = 0.6      # For piercing/dark cloud
MIN_GAP_PIERCING = 0.5             # For piercing/dark cloud
MAX_BULLISH = 50
MAX_BEARISH = 50
STRICT_ENGULFING_HARAMI = True     # Toggle for strict harami engulfing

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

# === Consolidated Pattern Detection ===
def detect_candlestick_patterns(df):
    patterns = []
    trend_cache = {}

    print("Scanning for all double candlestick patterns...")
    for i in tqdm(range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 2, len(df))):
        c1 = df.iloc[i - 2]  # t-2
        c2 = df.iloc[i - 1]  # t-1
        trends = determine_trends(df, i - 1, trend_cache)
        avg_price = (c1['close'] + c2['close']) / 2

        # Stop if max patterns reached for both bullish and bearish
        bullish_counts = {p: sum(1 for x in patterns if x['pattern'] == p) for p in [
            'bullish_engulfing', 'bullish_harami', 'bullish_homing_pigeon', 'bullish_kicking',
            'matching_low', 'piercing_line', 'bullish_separating', 'tweezer_bottom']}
        bearish_counts = {p: sum(1 for x in patterns if x['pattern'] == p) for p in [
            'bearish_engulfing', 'bearish_harami', 'bearish_homing_pigeon', 'bearish_kicking',
            'matching_high', 'dark_cloud_cover', 'bearish_separating', 'tweezer_top']}

        if all(count >= MAX_BULLISH for count in bullish_counts.values()) and \
           all(count >= MAX_BEARISH for count in bearish_counts.values()):
            break

        # === Bullish Engulfing ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and  # First candle bearish
            c2['close'] > c2['open'] and  # Second candle bullish
            c2['high'] >= c1['high'] and  # Second candle reaches equal or higher high
            c2['low'] <= c1['low'] and    # Second candle reaches equal or lower low
            c2['open'] < c1['close'] and  # Open below first candle's close
            c2['close'] > c1['open'] and  # Close above first candle's open
            bullish_counts.get('bullish_engulfing', 0) < MAX_BULLISH
        ):
            strength = 'strong' if (c2['high'] > c1['high'] and c2['low'] < c1['low']) else 'weak'
            impact = 'Strong Bullish Reversal' if strength == 'strong' else 'Weak Bullish Reversal'
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_engulfing',
                'strength': strength,
                'impact': impact,
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Bearish Engulfing ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and  # First candle bullish
            c2['close'] < c2['open'] and  # Second candle bearish
            c2['high'] >= c1['high'] and  # Second candle reaches equal or higher high
            c2['low'] <= c1['low'] and    # Second candle reaches equal or lower low
            c2['open'] > c1['close'] and  # Open above first candle's close
            c2['close'] < c1['open'] and  # Close below first candle's open
            bearish_counts.get('bearish_engulfing', 0) < MAX_BEARISH
        ):
            strength = 'strong' if (c2['high'] > c1['high'] and c2['low'] < c1['low']) else 'weak'
            impact = 'Strong Bearish Reversal' if strength == 'strong' else 'Weak Bearish Reversal'
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_engulfing',
                'strength': strength,
                'impact': impact,
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Bullish Harami ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and  # bearish
            c2['close'] > c2['open'] and  # bullish
            bullish_counts.get('bullish_harami', 0) < MAX_BULLISH
        ):
            if STRICT_ENGULFING_HARAMI:
                valid = c2['high'] <= c1['open'] and c2['low'] >= c1['close']
            else:
                valid = c2['open'] > c1['close'] and c2['close'] < c1['open']
            if valid:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'bullish_harami',
                    'impact': 'Potential Bullish Reversal',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': c2['close']
                })

        # === Bearish Harami ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and  # bullish
            c2['close'] < c2['open'] and  # bearish
            bearish_counts.get('bearish_harami', 0) < MAX_BEARISH
        ):
            if STRICT_ENGULFING_HARAMI:
                valid = c2['high'] <= c1['close'] and c2['low'] >= c1['open']
            else:
                valid = c2['open'] < c1['close'] and c2['close'] > c1['open']
            if valid:
                patterns.append({
                    'idx': i - 1,
                    'pattern': 'bearish_harami',
                    'impact': 'Potential Bearish Reversal',
                    'short_term_trend': trends['short_term'],
                    'long_term_trend': trends['long_term'],
                    'key_price': c2['close']
                })

        # === Bullish Homing Pigeon ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] < c2['open'] and
            c2['open'] > c1['close'] and c2['close'] < c1['open'] and
            bullish_counts.get('bullish_homing_pigeon', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_homing_pigeon',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Bearish Homing Pigeon ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] > c2['open'] and
            c2['open'] < c1['close'] and c2['close'] > c1['open'] and
            bearish_counts.get('bearish_homing_pigeon', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_homing_pigeon',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Bullish Kicking ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and
            c2['open'] > c1['close'] + PRICE_TOLERANCE_ENGULFING and
            c2['open'] > c1['open'] + PRICE_TOLERANCE_ENGULFING and
            bullish_counts.get('bullish_kicking', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_kicking',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Bearish Kicking ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] < c2['open'] and
            c2['open'] < c1['open'] - PRICE_TOLERANCE_ENGULFING and
            c2['open'] < c1['close'] - PRICE_TOLERANCE_ENGULFING and
            bearish_counts.get('bearish_kicking', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_kicking',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Matching Low ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] < c2['open'] and
            c2['open'] > c1['close'] and
            abs(c2['close'] - c1['close']) <= c1['close'] * PRICE_TOLERANCE_MATCHING and
            bullish_counts.get('matching_low', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'matching_low',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['close']
            })

        # === Matching High ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] > c2['open'] and
            c2['open'] < c1['close'] and
            abs(c2['close'] - c1['close']) <= c1['close'] * PRICE_TOLERANCE_MATCHING and
            bearish_counts.get('matching_high', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'matching_high',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['close']
            })

        # === On Neck ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            c2['close'] > c2['open'] and
            abs(c1['close'] - c1['open']) > (c1['high'] - c1['low']) * 0.6 and  # Long bearish
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) and   # Small bullish
            c2['open'] < c1['close'] and
            abs(c2['close'] - min(c1['open'], c1['close'])) < (abs(c1['close'] - c1['open']) * 0.1)
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'on_neck',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === In Neck ===
        elif (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and
            c2['close'] > c2['open'] and
            abs(c1['close'] - c1['open']) > (c1['high'] - c1['low']) * 0.6 and  # Long bearish
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) and   # Small bullish
            c2['open'] < c1['close'] and
            c2['close'] > min(c1['open'], c1['close']) and
            c2['close'] < max(c1['open'], c1['close'])
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'in_neck',
                'impact': 'Moderate Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['close']
            })

        # === Piercing Line ===
        c1_body = abs(c1['close'] - c1['open'])
        c1_range = c1['high'] - c1['low']
        c2_body = abs(c2['close'] - c2['open'])
        c2_range = c2['high'] - c2['low']
        c1_long = c1_range > 0 and c1_body / c1_range >= MIN_BODY_RATIO_PIERCING
        c2_long = c2_range > 0 and c2_body / c2_range >= MIN_BODY_RATIO_PIERCING

        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and
            c1_long and c2_long and
            c2['open'] < c1['close'] - MIN_GAP_PIERCING and
            c2['close'] > c1['open'] + MIN_GAP_PIERCING and
            bullish_counts.get('piercing_line', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'piercing_line',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['open']
            })

        # === Dark Cloud Cover ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] < c2['open'] and
            c1_long and c2_long and
            c2['open'] > c1['close'] + MIN_GAP_PIERCING and
            c2['close'] < c1['open'] - MIN_GAP_PIERCING and
            bearish_counts.get('dark_cloud_cover', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'dark_cloud_cover',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['open']
            })

        # === Bullish Separating Line ===
        if (
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and
            (abs(c2['open'] - c1['open']) <= OPEN_TOLERANCE_SEPARATING or c2['open'] > c1['open']) and
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            bullish_counts.get('bullish_separating', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bullish_separating',
                'impact': 'Bullish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['open']
            })

        # === Bearish Separating Line ===
        elif (
            c1['close'] > c1['open'] and c2['close'] < c2['open'] and
            abs(c2['open'] - c1['open']) <= OPEN_TOLERANCE_SEPARATING and
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            bearish_counts.get('bearish_separating', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'bearish_separating',
                'impact': 'Bearish Continuation',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c2['open']
            })

        # === Tweezer Bottom ===
        if (
            trends['short_term'] == 'down' and trends['long_term'] == 'down' and
            c1['close'] < c1['open'] and c2['close'] > c2['open'] and
            abs(c1['low'] - c2['low']) <= (avg_price * 0.00001) and
            bullish_counts.get('tweezer_bottom', 0) < MAX_BULLISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'tweezer_bottom',
                'impact': 'Potential Bullish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['low']
            })

        # === Tweezer Top ===
        elif (
            trends['short_term'] == 'up' and trends['long_term'] == 'up' and
            c1['close'] > c1['open'] and c2['close'] < c2['open'] and
            abs(c1['high'] - c2['high']) <= (avg_price * 0.00001) and
            bearish_counts.get('tweezer_top', 0) < MAX_BEARISH
        ):
            patterns.append({
                'idx': i - 1,
                'pattern': 'tweezer_top',
                'impact': 'Potential Bearish Reversal',
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'key_price': c1['high']
            })

    return patterns

# === Main Analysis Function ===
def run_analysis(data_file):
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    patterns = detect_candlestick_patterns(df)

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