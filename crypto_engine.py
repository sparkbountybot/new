#!/usr/bin/env python3
"""
Crypto Trading Engine — Uses data.alpaca.markets bars (unlocked via policy)
- Fetches historical bars from data.alpaca.markets
- Calculates technical indicators (RSI, MACD, Bollinger)
- Executes trades via api.alpaca.markets (already working)
- Full circle: data → signals → execution → P&L tracking
"""
import json, os, sys, math, time, argparse
from datetime import datetime

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client


class CryptoEngine:
    def __init__(self):
        self.client = create_alpaca_client(paper=False)
        self.base_data = "https://data.alpaca.markets"
        self.base_api = "api.alpaca.markets"
        self.key = os.environ.get('ALPACA_API_KEY', '')
        self.secret = os.environ.get('ALPACA_SECRET_KEY', '')
        
        # Load API keys from config if env vars not set
        if not self.key or not self.secret:
            import yaml
            config = yaml.safe_load(open('/sandbox/new/config.yaml'))
            self.key = config['trading_live']['alpaca_api_key']
            self.secret = config['trading_live']['alpaca_secret_key']
        
        self.hdrs = {
            'APCA-API-KEY-ID': self.key,
            'APCA-API-SECRET-KEY': self.secret
        }
        
        self.trades_file = "/sandbox/new/data/crypto_trades.json"
        self.trades = []
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file) as f:
                    self.trades = json.load(f)
            except:
                self.trades = []
        
        # Crypto pairs to trade
        self.pairs = ['BTC/USD', 'ETH/USD']
    
    def get_bars(self, symbol, start='2026-09-01', end='2026-09-03', timeframe='1D'):
        """Fetch historical bars from data.alpaca.markets via curl subprocess"""
        import subprocess
        
        # Use host's curl which has policy access
        cmd = (
            f'curl -s --max-time 5 "https://data.alpaca.markets/v1beta3/crypto/us/bars'
            f'?start={start}&end={end}&timeframe={timeframe}&symbols={symbol}" '
            f'-H "APCA-API-KEY-ID: {self.key}" '
            f'-H "APCA-API-SECRET-KEY: {self.secret}"'
        )
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return data.get('bars', {}).get(symbol, [])
            else:
                print(f"  Curl error: {result.stderr[:200]}")
                return []
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            return []
    
    def calc_rsi(self, prices, period=14):
        """Calculate RSI from price list"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calc_macd(self, prices, fast=12, slow=26):
        """Calculate MACD line"""
        if len(prices) < slow:
            return 0
        
        def ema(prices, period):
            if not prices:
                return 0
            multiplier = 2 / (period + 1)
            ema_val = sum(prices[:period]) / period
            for price in prices[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val
        
        return ema(prices, fast) - ema(prices, slow)
    
    def calc_bollinger(self, prices, period=20):
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return (0, 0, 0)
        
        window = prices[-period:]
        sma = sum(window) / len(window)
        std = math.sqrt(sum((p - sma) ** 2 for p in window) / len(window))
        
        return (sma + (std * 2), sma, sma - (std * 2))
    
    def analyze(self, symbol, bars):
        """Generate trading signal from bars data"""
        if not bars or len(bars) < 30:
            return "HOLD", 0.0, "insufficient data"
        
        # Extract prices
        closes = [b['c'] for b in bars]
        highs = [b['h'] for b in bars]
        lows = [b['l'] for b in bars]
        
        current_price = closes[-1]
        price_change = (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else 0
        high_24h = max(highs[-3:]) if len(highs) >= 3 else current_price
        low_24h = min(lows[-3:]) if len(lows) >= 3 else current_price
        
        # Calculate indicators
        rsi = self.calc_rsi(closes)
        macd = self.calc_macd(closes)
        bb_upper, bb_mid, bb_lower = self.calc_bollinger(closes)
        
        # Volume trend
        volumes = [b['v'] for b in bars]
        avg_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1]
        last_vol = volumes[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0
        
        signals = []
        
        # Buy signals
        if rsi < 30:
            signals.append(("BUY", f"RSI oversold {rsi:.1f}"))
        elif current_price < bb_lower * 1.01 and price_change < -2:
            signals.append(("BUY", f"below BB lower ${bb_lower:.2f}"))
        elif macd > 0 and closes[-1] > closes[-2]:
            signals.append(("BUY", f"MACD positive"))
        
        # Sell signals
        elif rsi > 70:
            signals.append(("SELL", f"RSI overbought {rsi:.1f}"))
        elif current_price > bb_upper * 0.99 and price_change > 2:
            signals.append(("SELL", f"above BB upper ${bb_upper:.2f}"))
        
        if not signals:
            return "HOLD", 0.0, f"RSI={rsi:.1f} MACD={macd:.2f} BB=({bb_upper:.2f},{bb_mid:.2f},{bb_lower:.2f})"
        
        reason = f"{signals[0][1]}"
        if len(signals) > 1:
            reason += f" + {signals[1][1]}"
        
        return signals[0][0], price_change, reason
    
    def get_position(self, symbol):
        """Get crypto position from portfolio"""
        pos_list = self.client.get_positions() or []
        for p in pos_list:
            if p.get('symbol') == symbol:
                return {
                    'qty': float(p.get('qty', 0)),
                    'entry': float(p.get('avg_entry_price', 0)),
                    'current': float(p.get('current_price', 0)),
                    'pl': float(p.get('unrealized_pl', 0)),
                    'plpct': float(p.get('unrealized_plpc', 0)) * 100
                }
        return None
    
    def submit_order(self, symbol, qty, side):
        """Submit crypto order via api.alpaca.markets"""
        order = {
            'symbol': symbol,
            'qty': str(qty),
            'side': side,
            'type': 'market',
            'time_in_force': 'day'
        }
        
        result = self.client.post("/v2/orders", order)
        if result and isinstance(result, dict):
            return result
        return None
    
    def calculate_size(self, symbol, current_price, risk_pct=0.05):
        """Calculate position size based on equity"""
        acct = self.client.get_account()
        equity = float(acct.get('equity', 0))
        
        # Risk 5% of equity per position
        risk_amount = equity * risk_pct
        
        # Max position: 10% of equity
        max_position = equity * 0.10
        
        size = min(risk_amount, max_position) / current_price
        return max(0.001, round(size, 8))  # Min 0.001 crypto
    
    def cycle(self):
        """Main cycle: fetch data, analyze, execute"""
        try:
            acct = self.client.get_account()
            equity = float(acct.get('equity', 0))
            cash = float(acct.get('cash', 0))
            
            print(f"\n=== CRYPTO ENGINE CYCLE {datetime.now().strftime('%H:%M')} ===")
            print(f"  E:${equity:,.0f}  C:${cash:,.0f}")
            
            # Fetch bars for each pair
            results = {}
            for symbol in self.pairs:
                print(f"\n--- {symbol} ---")
                
                bars = self.get_bars(symbol)
                if not bars:
                    print(f"  No bars data")
                    continue
                
                signal, pct_change, reason = self.analyze(symbol, bars)
                current_price = bars[-1]['c']
                
                print(f"  Price: ${current_price:,.2f} | Change: {pct_change:+.2f}%")
                print(f"  RSI: {self.calc_rsi([b['c'] for b in bars]):.1f}")
                print(f"  MACD: {self.calc_macd([b['c'] for b in bars]):.2f}")
                print(f"  Signal: {signal} — {reason}")
                
                results[symbol] = {
                    'signal': signal,
                    'price': current_price,
                    'bars': len(bars),
                    'reason': reason
                }
                
                # Execute trades
                if signal == "BUY":
                    pos = self.get_position(symbol)
                    if not pos or pos['qty'] < 0.001:
                        qty = self.calculate_size(symbol, current_price)
                        order = self.submit_order(symbol, qty, "buy")
                        if order and order.get('status'):
                            print(f"  ✅ BOUGHT {qty:.4f} {symbol} @ ${current_price:.2f}")
                            self.trades.append({
                                'ts': datetime.now().isoformat(),
                                'action': 'BUY',
                                'symbol': symbol,
                                'qty': qty,
                                'price': current_price,
                                'reason': reason,
                                'type': 'crypto'
                            })
                        else:
                            print(f"  ❌ BUY failed")
                
                elif signal == "SELL":
                    pos = self.get_position(symbol)
                    if pos and pos['qty'] > 0.001:
                        order = self.submit_order(symbol, pos['qty'], "sell")
                        if order and order.get('status'):
                            print(f"  ✅ SOLD {pos['qty']:.4f} {symbol} @ ${current_price:.2f}")
                            self.trades.append({
                                'ts': datetime.now().isoformat(),
                                'action': 'SELL',
                                'symbol': symbol,
                                'qty': pos['qty'],
                                'price': current_price,
                                'reason': reason,
                                'type': 'crypto'
                            })
                        else:
                            print(f"  ❌ SELL failed")
                
                time.sleep(0.5)  # Rate limit
            
            # Save trades
            self._save_trades()
            
            # Final status
            print(f"\n=== FINAL POSITIONS ===")
            pos_list = self.client.get_positions() or []
            crypto_pos = [p for p in pos_list if '/' in p.get('symbol', '')]
            for p in crypto_pos:
                qty = float(p.get('qty', 0))
                entry = float(p.get('avg_entry_price', 0))
                current = float(p.get('current_price', 0))
                pl = float(p.get('unrealized_pl', 0))
                print(f"  {p['symbol']}: {qty:.4f} @ ${entry:.2f} → ${current:.2f} PL: ${pl:+,.2f}")
            
            if not crypto_pos:
                print("  No crypto positions")
            
            return results
            
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _save_trades(self):
        os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
        with open(self.trades_file, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def status(self):
        """Quick status without executing trades"""
        acct = self.client.get_account()
        equity = float(acct.get('equity', 0))
        cash = float(acct.get('cash', 0))
        
        print(f"\n=== CRYPTO ENGINE STATUS ===")
        print(f"  E:${equity:,.0f}  C:${cash:,.0f}")
        
        # Check positions
        pos_list = self.client.get_positions() or []
        crypto_pos = [p for p in pos_list if '/' in p.get('symbol', '')]
        
        if crypto_pos:
            print(f"\n  POSITIONS ({len(crypto_pos)}):")
            for p in crypto_pos:
                qty = float(p.get('qty', 0))
                entry = float(p.get('avg_entry_price', 0))
                current = float(p.get('current_price', 0))
                pl = float(p.get('unrealized_pl', 0))
                print(f"    {p['symbol']}: {qty:.4f} @ ${entry:.2f} → ${current:.2f} PL: ${pl:+,.2f}")
        else:
            print(f"\n  No crypto positions")
        
        # Check trades log
        if os.path.exists(self.trades_file):
            with open(self.trades_file) as f:
                trades = json.load(f)
            if trades:
                print(f"\n  TRADED {len(trades)} crypto trades")
                buys = [t for t in trades if t.get('action') == 'BUY']
                sells = [t for t in trades if t.get('action') == 'SELL']
                print(f"    {len(buys)} buys, {len(sells)} sells")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run cycle (fetch, analyze, execute)")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--pairs", nargs="*", default=['BTC/USD', 'ETH/USD'], help="Crypto pairs to trade")
    
    args = parser.parse_args()
    
    engine = CryptoEngine()
    engine.pairs = args.pairs
    
    if args.run:
        engine.cycle()
    elif args.status:
        engine.status()
    else:
        engine.status()
        print(f"\nUSAGE:")
        print(f"  python3 crypto_engine.py --status    : check positions")
        print(f"  python3 crypto_engine.py --run       : fetch data, analyze, trade")
        print(f"  python3 crypto_engine.py --pairs BTC/USD ETH/USD DOGE/USD : specific pairs")
