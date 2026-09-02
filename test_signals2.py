"""Test with 40-bar data to generate oversold signals."""
import random
import numpy as np
from strategies import MeanReversionStrategy, Bar

random.seed(42)
strategy = MeanReversionStrategy()

def make_bars(base_price, trend_days, crash_days, flat_days):
    bars = []
    price = base_price
    # Trend phase
    for i in range(trend_days):
        daily_change = random.uniform(0.01, 0.025)
        o = round(price * 1.001, 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.003, 2)
        l = round(min(o, c) * 0.997, 2)
        bars.append(Bar(i, o, h, l, c, random.randint(20_000_000, 40_000_000)))
        price = c

    # Crash phase - very aggressive
    for i in range(crash_days):
        daily_change = random.uniform(-0.06, -0.03)  # -3% to -6% daily
        o = round(price * (1 + random.gauss(0, 0.005)), 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.002, 2)
        l = round(min(o, c) * 0.995, 2)
        bars.append(Bar(trend_days + i, o, h, l, c, random.randint(40_000_000, 80_000_000)))
        price = c

    # Flat phase - stay oversold
    for i in range(flat_days):
        daily_change = random.gauss(-0.005, 0.01)  # small downward drift
        o = round(price * (1 + random.gauss(0, 0.003)), 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.001, 2)
        l = round(min(o, c) * 0.995, 2)
        bars.append(Bar(trend_days + crash_days + i, o, h, l, c, random.randint(25_000_000, 50_000_000)))
        price = c

    return bars

# Test NVDA pattern
print("=== Testing NVDA with extreme oversold ===")
nvda_bars = make_bars(217.0, 25, 8, 7)  # 25 days up, 8 days crash, 7 flat
closes = [b.close for b in nvda_bars]
print(f"Bars: {len(nvda_bars)}")
print(f"Start: ${closes[0]:.2f}, Low: ${min(closes):.2f}, Current: ${closes[-1]:.2f}")

bb = strategy._bollinger_bands(closes)
print(f"BB Lower: ${bb[2]:.2f}, Current: ${closes[-1]:.2f}, Below? {closes[-1] < bb[2]}")

deltas = np.diff(closes)
gains = np.where(deltas > 0, deltas, 0)
losses = np.where(deltas < 0, -deltas, 0)
avg_gain = np.mean(gains[-14:])
avg_loss = np.mean(losses[-14:])
rs = avg_gain / avg_loss if avg_loss > 0 else 100
rsi = 100 - (100 / (1 + rs))
print(f"RSI: {rsi:.1f}")

# Scan all bars for signals
print("\nSignal scan:")
for i in range(20, len(nvda_bars)):
    window = nvda_bars[max(0,i-60):i]
    sig = strategy.analyze(window)
    if sig:
        print(f"  Bar {i}: {sig.direction} conf={sig.confidence:.2f} entry=${sig.entry_price:.2f}")

# Try different seeds
print("\n=== Trying multiple seeds ===")
for seed in [1, 2, 3, 5, 7, 11, 13]:
    random.seed(seed)
    bars = make_bars(217.0, 25, 8, 7)
    closes = [b.close for b in bars]
    
    bb = strategy._bollinger_bands(closes)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    rsi = 100 - (100 / (1 + np.mean(gains[-14:])/np.mean(losses[-14:]))) if np.mean(losses[-14:]) > 0 else 100
    
    signals_found = False
    for i in range(20, len(bars)):
        sig = strategy.analyze(bars[max(0,i-60):i])
        if sig:
            signals_found = True
            break
    
    status = "✅ SIGNAL" if signals_found else "❌ no signal"
    print(f"  Seed {seed:3d}: RSI={rsi:5.1f} BelowBB={closes[-1]<bb[2]} {status}")
