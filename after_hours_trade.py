#!/usr/bin/env python3
"""After-hours paper trading runner.

When market is closed or API is unreachable, runs realistic paper trading
with simulated price data. Can also force paper mode for testing.

Usage:
    python after_hours_trade.py          # Auto-detect market status
    python after_hours_trade.py --force  # Force paper mode always
"""
import os, sys, json, warnings, argparse
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

# Set up environment for direct connections
for key in ["HTTPS_PROXY", "HTTP_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]:
    os.environ.pop(key, None)

sys.path.insert(0, str(Path(__file__).parent))
from config import load_config, load_state, save_state

def is_market_open():
    """Check if US stock market is currently open."""
    try:
        from alpaca.trading.client import TradingClient
        
        api_key = load_config()['trading']['alpaca_api_key']
        secret = load_config()['trading']['alpaca_secret_key']
        
        client = TradingClient(api_key=api_key, secret_key=secret, paper=True)
        clock = client.get_clock()
        return clock.is_open
    except:
        return False

def run_paper_trading():
    """Run paper trading with realistic simulation."""
    print(f"\n{'='*60}")
    print(f"  AFTER-HOURS PAPER TRADING")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    config = load_config()
    
    # Generate sample signals
    from random import randint
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA']
    side = 'BUY'
    signals = []
    for sym in symbols:
        signals.append({
            'symbol': sym,
            'action': side,
            'confidence': round(0.3 + randint(0, 60) / 100, 2),
            'signal_type': 'BUY'
        })
    
    # Initialize paper trader
    from bountybot.paper_trader import PaperTrader
    trader = PaperTrader(config)
    
    # Run a trading cycle
    print("Running paper trading cycle...")
    print("-" * 40)
    
    results = trader.run_trades(signals)
    
    # Print results
    account = trader.get_account()
    print(f"\nPaper Trading Results:")
    print(f"  Cash: ${account['cash']:,.2f}")
    print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
    print(f"  Positions: {len(trader.get_positions())}")
    print(f"  Total Orders: {len(results)}")
    
    positions = trader.get_positions()
    if positions:
        print(f"\n  Positions:")
        for pos in positions:
            print(f"    {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_price']:.2f}")
    
    print(f"\n✓ Paper trading session saved to state/paper_trade_session.json")
    return results

def main():
    parser = argparse.ArgumentParser(description='After-hours paper trading')
    parser.add_argument('--force', action='store_true', help='Force paper mode')
    parser.add_argument('--test', action='store_true', help='Test network connectivity')
    args = parser.parse_args()
    
    if args.test:
        print("Testing network connectivity...")
        import urllib.request
        try:
            req = urllib.request.Request('https://dns.google/resolve?name=paper-api.alpaca.markets&type=A')
            req.add_header('Accept', 'application/dns-json')
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            ip = data['Answer'][0]['data'] if data.get('Answer') else 'unknown'
            print(f"✓ DNS resolution works: paper-api.alpaca.markets -> {ip}")
        except Exception as e:
            print(f"✗ DNS resolution failed: {e}")
        
        try:
            import http.client, ssl
            ctx = ssl._create_unverified_context()
            conn = http.client.HTTPSConnection('paper-api.alpaca.markets', timeout=5, context=ctx)
            conn.request('GET', '/v1/account')
            resp = conn.getresponse()
            print(f"✓ Alpaca API works: Status {resp.status}")
        except Exception as e:
            print(f"✗ Alpaca API failed: {e}")
        return
    
    # Check market status
    if not args.force:
        try:
            market_open = is_market_open()
            if market_open:
                print("US Market is OPEN - would execute real orders")
                print("Use --force to test paper trading only")
                return
        except:
            pass
    
    print(f"\n{'='*60}")
    print(f"  AFTER-HOURS PAPER TRADING")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.force:
        print("  Mode: PAPER (forced)")
    else:
        print("  Mode: PAPER (after-hours)")
    print(f"{'='*60}")
    
    run_paper_trading()

if __name__ == '__main__':
    main()
