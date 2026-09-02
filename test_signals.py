"""Test strategy signal generation with extreme data."""
import random, numpy as np
from strategies import MeanReversionStrategy, Bar

random.seed(99)
base_price = 324.00
bars = []
price = base_price

# Days 1-20: strong uptrend
for i in range(20):
    change = 0.015 + random.gauss(0, 0.005)
    open_price = price * (1 + random.gauss(0, 0.002))
    close_price = price * (1 + change)
    high = max(open_price, close_price) * 1.005
    low = min(open_price, close_price) * 0.995
    bars.append(Bar(i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(15_000_000, 40_000_000)))
    price = close_price

print(f'After 20 days of uptrend: ${price:.2f}')

# Days 21-27: EXTREME crash - 5-8% daily
for i in range(7):
    change = -0.05 - random.uniform(0, 0.03)
    open_price = price * (1 + random.gauss(0, 0.003))
    close_price = price * (1 + change)
    high = max(open_price, close_price) * 1.002
    low = min(open_price, close_price) * 0.995
    bars.append(Bar(20+i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(50_000_000, 90_000_000)))
    price = close_price

# Days 28-30: continue falling
for i in range(3):
    change = -0.02 + random.gauss(0, 0.01)
    open_price = price * (1 + random.gauss(0, 0.002))
    close_price = price * (1 + change)
    high = max(open_price, close_price) * 1.002
    low = min(open_price, close_price) * 0.995
    bars.append(Bar(27+i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(30_000_000, 60_000_000)))
    price = close_price

print(f'After crash: ${bars[-1].close:.2f}')
total_drop = ((bars[-1].close/bars[0].open) - 1) * 100
print(f'Total drop: {total_drop:.1f}%')

strategy = MeanReversionStrategy()
closes = [b.close for b in bars]

bb = strategy._bollinger_bands(closes)
print(f'\nBollinger Bands:')
print(f'  Upper: ${bb[0]:.2f}')
print(f'  Middle: ${bb[1]:.2f}')
print(f'  Lower: ${bb[2]:.2f}')
print(f'  Current: ${bars[-1].close:.2f}')
print(f'  Below BB Lower? {bars[-1].close < bb[2]} (${bars[-1].close:.2f} < ${bb[2]:.2f})')

deltas = np.diff(closes)
gains = np.where(deltas > 0, deltas, 0)
losses = np.where(deltas < 0, -deltas, 0)
avg_gain = np.mean(gains[-14:])
avg_loss = np.mean(losses[-14:])
rs = avg_gain / avg_loss if avg_loss > 0 else 100
rsi = 100 - (100 / (1 + rs))
print(f'\nRSI: {rsi:.1f} (need < 30)')

print(f'\nStrategy scan:')
for i in range(20, len(bars)):
    window = bars[max(0, i-60):i]
    sig = strategy.analyze(window)
    if sig:
        print(f'  Bar {i}: {sig.direction} conf={sig.confidence:.2f} entry=${sig.entry_price:.2f}')

# Also try with more bars (40 days total)
print('\n--- With 40 bars ---')
bars2 = []
price2 = base_price
for i in range(28):  # 28 days of uptrend
    change = 0.012 + random.gauss(0, 0.005)
    open_price = price2 * (1 + random.gauss(0, 0.002))
    close_price = price2 * (1 + change)
    high = max(open_price, close_price) * 1.005
    low = min(open_price, close_price) * 0.995
    bars2.append(Bar(i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(15_000_000, 40_000_000)))
    price2 = close_price

# Then crash
for i in range(6):
    change = -0.06 - random.uniform(0, 0.02)
    open_price = price2 * (1 + random.gauss(0, 0.003))
    close_price = price2 * (1 + change)
    high = max(open_price, close_price) * 1.002
    low = min(open_price, close_price) * 0.995
    bars2.append(Bar(28+i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(50_000_000, 90_000_000)))
    price2 = close_price

# Last few bars flat
for i in range(6):
    change = -0.01 + random.gauss(0, 0.005)
    open_price = price2 * (1 + random.gauss(0, 0.002))
    close_price = price2 * (1 + change)
    high = max(open_price, close_price) * 1.002
    low = min(open_price, close_price) * 0.995
    bars2.append(Bar(34+i, round(open_price, 2), round(high, 2), round(low, 2), round(close_price, 2), random.randint(30_000_000, 60_000_000)))

print(f'Total bars: {len(bars2)}')
bb2 = strategy._bollinger_bands([b.close for b in bars2])
deltas2 = np.diff([b.close for b in bars2])
gains2 = np.where(deltas2 > 0, deltas2, 0)
losses2 = np.where(deltas2 < 0, -deltas2, 0)
avg_gain2 = np.mean(gains2[-14:])
avg_loss2 = np.mean(losses2[-14:])
rs2 = avg_gain2 / avg_loss2 if avg_loss2 > 0 else 100
rsi2 = 100 - (100 / (1 + rs2))
print(f'RSI: {rsi2:.1f}')
print(f'BB Lower: ${bb2[2]:.2f}, Last Close: ${bars2[-1].close:.2f}')
print(f'Below BB? {bars2[-1].close < bb2[2]}')

print(f'\nStrategy scan on 40 bars:')
for i in range(20, len(bars2)):
    window = bars2[max(0, i-60):i]
    sig = strategy.analyze(window)
    if sig:
        print(f'  Bar {i}: {sig.direction} conf={sig.confidence:.2f} entry=${sig.entry_price:.2f}')
