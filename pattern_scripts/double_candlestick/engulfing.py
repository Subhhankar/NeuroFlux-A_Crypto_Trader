import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import numpy as np

# Configurations
IMAGE_WIDTH = 1500
IMAGE_HEIGHT = 800
OUTPUT_DIR = "engulfing_patterns"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHORT_TERM_PERIOD = 20
LONG_TERM_PERIOD = 50
MAX_BULLISH_PATTERNS = 50
MAX_BEARISH_PATTERNS = 50
PRICE_TOLERANCE = 0.0015  # 0.15% tolerance for high/low equality

def determine_trends(df, idx, cache):
    """Efficient trend lookup with caching"""
    if idx in cache:
        return cache[idx]
    
    trends = {'short_term': 'neutral', 'long_term': 'neutral'}
    
    if idx >= SHORT_TERM_PERIOD:
        short_change = (df.loc[idx, 'close'] - df.loc[idx - SHORT_TERM_PERIOD, 'close']) / df.loc[idx - SHORT_TERM_PERIOD, 'close']
        trends['short_term'] = 'up' if short_change > 0 else 'down'
    
    if idx >= LONG_TERM_PERIOD:
        long_change = (df.loc[idx, 'close'] - df.loc[idx - LONG_TERM_PERIOD, 'close']) / df.loc[idx - LONG_TERM_PERIOD, 'close']
        trends['long_term'] = 'up' if long_change > 0 else 'down'
    
    cache[idx] = trends
    return trends

def detect_engulfing(df, idx, trend_cache):
    """Detect engulfing patterns with strict range engulfment requirements"""
    if idx < 2:
        return None

    candle1 = df.iloc[idx - 2]  # t-2
    candle2 = df.iloc[idx - 1]  # t-1
    trends = determine_trends(df, idx - 1, trend_cache)
    avg_price = (candle1['close'] + candle2['close']) / 2

    # Bullish Engulfing
    if (trends['short_term'] == 'down' and trends['long_term'] == 'down' and
        candle1['close'] < candle1['open'] and  # First candle is bearish
        candle2['close'] > candle2['open']):    # Second candle is bullish
        
        # Strict engulfment requirements
        if (candle2['high'] >= candle1['high'] and  # Second candle must reach equal or higher high
            candle2['low'] <= candle1['low'] and    # Second candle must reach equal or lower low
            candle2['open'] < candle1['close'] and  # Open must be below first candle's close
            candle2['close'] > candle1['open']):    # Close must be above first candle's open
            
            # Check if it's a strong engulfment (both high and low fully engulfed)
            if (candle2['high'] > candle1['high'] and 
                candle2['low'] < candle1['low']):
                strength = 'strong'
                impact = 'Strong Bullish Reversal'
            else:
                strength = 'weak'
                impact = 'Weak Bullish Reversal'
            
            return {
                'idx': idx - 1,
                'pattern': 'bullish_engulfing',
                'strength': strength,
                'impact': impact,
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'confirmation_price': candle2['close']
            }

    # Bearish Engulfing
    elif (trends['short_term'] == 'up' and trends['long_term'] == 'up' and
          candle1['close'] > candle1['open'] and  # First candle is bullish
          candle2['close'] < candle2['open']):    # Second candle is bearish
          
        # Strict engulfment requirements
        if (candle2['high'] >= candle1['high'] and  # Second candle must reach equal or higher high
            candle2['low'] <= candle1['low'] and    # Second candle must reach equal or lower low
            candle2['open'] > candle1['close'] and  # Open must be above first candle's close
            candle2['close'] < candle1['open']):   # Close must be below first candle's open
            
            # Check if it's a strong engulfment (both high and low fully engulfed)
            if (candle2['high'] > candle1['high'] and 
                candle2['low'] < candle1['low']):
                strength = 'strong'
                impact = 'Strong Bearish Reversal'
            else:
                strength = 'weak'
                impact = 'Weak Bearish Reversal'
            
            return {
                'idx': idx - 1,
                'pattern': 'bearish_engulfing',
                'strength': strength,
                'impact': impact,
                'short_term_trend': trends['short_term'],
                'long_term_trend': trends['long_term'],
                'confirmation_price': candle2['close']
            }

    return None

def generate_chart(df, pattern_info, file_index):
    """Create chart with highlighted pattern and strength indication"""
    plt.style.use('seaborn')
    fig, ax = plt.subplots(figsize=(IMAGE_WIDTH / 100, IMAGE_HEIGHT / 100), dpi=100)
    
    pattern_idx = pattern_info['idx']
    t2_idx = pattern_idx - 1
    
    # Show 30 candles before and after
    start_idx = max(0, t2_idx - 30)
    end_idx = min(len(df), pattern_idx + 31)
    subset = df.iloc[start_idx:end_idx].reset_index(drop=True)
    
    # Find positions of pattern candles
    t2_pos = t2_idx - start_idx
    t1_pos = t2_pos + 1
    
    # Plot candles
    for i, row in subset.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
        ax.add_patch(patches.Rectangle(
            (i - 0.3, min(row['open'], row['close'])),
            0.6,
            abs(row['close'] - row['open']),
            facecolor=color,
            edgecolor=color
        ))

    # Draw key level line
    if pattern_info['pattern'] == 'bullish_engulfing':
        key_price = min(subset.iloc[t2_pos]['low'], subset.iloc[t1_pos]['low'])
        line_color = 'green'
        line_label = 'Support'
    else:
        key_price = max(subset.iloc[t2_pos]['high'], subset.iloc[t1_pos]['high'])
        line_color = 'red'
        line_label = 'Resistance'
    
    ax.axhline(y=key_price, color=line_color, linestyle=':', alpha=0.7, label=line_label)
    
    # Bounding box with strength-based color
    box_left = t2_pos - 0.5
    box_right = t1_pos + 0.5
    box_bottom = min(subset.iloc[t2_pos]['low'], subset.iloc[t1_pos]['low']) * 0.995
    box_top = max(subset.iloc[t2_pos]['high'], subset.iloc[t1_pos]['high']) * 1.005
    
    box_color = 'darkgreen' if (pattern_info['pattern'] == 'bullish_engulfing' and pattern_info['strength'] == 'strong') else 'limegreen'
    box_color = 'darkred' if (pattern_info['pattern'] == 'bearish_engulfing' and pattern_info['strength'] == 'strong') else 'lightcoral'
    
    ax.add_patch(patches.Rectangle(
        (box_left, box_bottom),
        box_right - box_left,
        box_top - box_bottom,
        fill=False,
        edgecolor=box_color,
        linewidth=2,
        linestyle='--' if pattern_info['strength'] == 'weak' else '-',
        zorder=10
    ))

    # Info box with strength indication
    info_text = (
        f"Pattern: {pattern_info['pattern'].replace('_', ' ').title()} ({pattern_info['strength'].upper()})\n"
        f"Impact: {pattern_info['impact']}\n"
        f"20-period Trend: {pattern_info['short_term_trend'].upper()}\n"
        f"50-period Trend: {pattern_info['long_term_trend'].upper()}\n"
        f"Date: {df.iloc[pattern_idx]['datetime_utc'].strftime('%Y-%m-%d')}\n"
        f"Key Price: {key_price:.4f}"
    )

    ax.text(
        0.05, 0.95, info_text,
        transform=ax.transAxes,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray', boxstyle='round'),
        fontsize=10
    )

    # X-axis ticks with dates
    xtick_positions = np.linspace(0, len(subset)-1, 10, dtype=int)
    xtick_labels = [subset.iloc[i]['datetime_utc'].strftime('%m-%d') for i in xtick_positions]
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, rotation=45)
    
    ax.legend(loc='upper left')
    ax.set_title(f"{pattern_info['pattern'].replace('_', ' ').title()} Pattern - {pattern_info['strength'].title()} Signal", fontsize=12)
    plt.tight_layout()

    # Save with consistent numbering
    filename = f"{file_index:03d}_{pattern_info['pattern']}_{pattern_info['strength']}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, filename), bbox_inches='tight', pad_inches=0.2)
    plt.close()

def main_analysis(data_file):
    """Main analysis function with strength classification"""
    df = pd.read_csv(data_file, parse_dates=['datetime_utc']).sort_values('datetime_utc')
    trend_cache = {}
    
    bullish_patterns = []
    bearish_patterns = []
    
    print("Scanning for engulfing patterns with strength classification...")
    
    for i in range(max(SHORT_TERM_PERIOD, LONG_TERM_PERIOD) + 2, len(df)):
        pattern = detect_engulfing(df, i, trend_cache)
        if pattern:
            if pattern['pattern'] == 'bullish_engulfing' and len(bullish_patterns) < MAX_BULLISH_PATTERNS:
                bullish_patterns.append(pattern)
            elif pattern['pattern'] == 'bearish_engulfing' and len(bearish_patterns) < MAX_BEARISH_PATTERNS:
                bearish_patterns.append(pattern)
            
            if len(bullish_patterns) >= MAX_BULLISH_PATTERNS and len(bearish_patterns) >= MAX_BEARISH_PATTERNS:
                break
    
    print(f"\nFound {len(bullish_patterns)} bullish and {len(bearish_patterns)} bearish patterns")
    print(f"Strong patterns: {sum(1 for p in bullish_patterns + bearish_patterns if p['strength'] == 'strong')}")
    print(f"Weak patterns: {sum(1 for p in bullish_patterns + bearish_patterns if p['strength'] == 'weak')}")
    
    # Generate charts
    print("\nGenerating pattern charts...")
    for i, pattern in enumerate(bullish_patterns[:MAX_BULLISH_PATTERNS]):
        generate_chart(df, pattern, i)
    
    for i, pattern in enumerate(bearish_patterns[:MAX_BEARISH_PATTERNS]):
        generate_chart(df, pattern, i + MAX_BULLISH_PATTERNS)
    
    print(f"\nGenerated {len(bullish_patterns)} bullish and {len(bearish_patterns)} bearish charts")
    print(f"Saved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main_analysis("OHCLV.csv")