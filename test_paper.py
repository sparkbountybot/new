#!/usr/bin/env python3
"""Test paper trading engine with real API balance."""
import subprocess, json, os, sys

sys.path.insert(0, '.')
from config import load_config, save_state
from bountybot.paper_trader import PaperTrader

def curl_api(endpoint, headers=None):
    """Make API call using curl subprocess."""
    api_key = 'PKYKHN5LV53HDV2GXRSDA6WJM6'
    secret = 'tzU24QxdnsugiCB5DUWb5bMZdVifBY5rfEhr2by4DiK'
    
    cmd = ['curl', '-s', '--max-time', '5', '-X', 'GET',
           '-H', f'APCA-API-KEY-ID: {api_key}',
           '-H', f'APCA-API-SECRET-KEY: {secret}',
           f'https://paper-api.alpaca.markets{endpoint}']
    
    if headers:
        for k, v in headers.items():
            cmd.extend(['-H', f'{k}: {v}'])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout:
        return json.loads(result.stdout)
    return None

print('=== Testing Paper Trading Engine ===\n')

# Get account info via curl
acct = curl_api('/v2/account')
if acct:
    print(f'Account Status: {acct.get("status")}')
    print(f'Portfolio Value: ${float(acct.get("portfolio_value", 0)):,.2f}')
    print(f'Buying Power: ${float(acct.get("buying_power", 0)):,.2f}')
    print(f'Equity: ${float(acct.get("equity", 0)):,.2f}')
    print(f'Cash: ${float(acct.get("cash", 0)):,.2f}\n')
else:
    print('API call failed')
    sys.exit(1)

# Now test paper trading engine with curl-based data fetching
config = load_config()
trader = PaperTrader(config)

# Generate sample signals
signals = [
    {'symbol': 'AAPL', 'action': 'BUY', 'confidence': 0.7, 'signal_type': 'BUY'},
    {'symbol': 'MSFT', 'action': 'SELL', 'confidence': 0.6, 'signal_type': 'SELL'},
    {'symbol': 'GOOGL', 'action': 'BUY', 'confidence': 0.8, 'signal_type': 'BUY'},
]

print(f'Running paper trades with {len(signals)} signals...')
results = trader.run_trades(signals)

print(f'\nResults:')
print(f'  Orders executed: {len(results)}')
for order in results:
    print(f'  {order["symbol"]}: {order["action"]} {order["qty"]} shares @ ${order.get("filled_price", 0):.2f}')

# Get account state
account = trader.get_account()
print(f'\nPaper Account State:')
print(f'  Cash: ${account["cash"]:,.2f}')
print(f'  Portfolio value: ${account["portfolio_value"]:,.2f}')
print(f'  Positions: {len(trader.get_positions())}')

# Save state
save_state('paper_trade_session', {
    'timestamp': '2026-09-01',
    'results': results,
    'account': account
})
print('\n✓ Paper trading session saved')
