#!/usr/bin/env python3
"""
LOAD ALPACA CREDENTIALS — Fix spark3 connection

Your Universal API Client wasn't loading creds from config.yaml.
This script fixes it and tests the connection.

Run: python3 load_creds.py
"""
import os
import sys
import warnings
import subprocess

warnings.filterwarnings('ignore')

print("=" * 60)
print("LOAD ALPACA CREDENTIALS — FIX SPARK3")
print("=" * 60)

# STEP 1: Load from config.yaml
print("\nChecking config.yaml...")
config_path = '/sandbox/new/config.yaml'

if os.path.exists(config_path):
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        
        trading = config.get('trading', {})
        if trading.get('alpaca_api_key'):
            api_key = trading['alpaca_api_key']
            api_secret = trading['alpaca_secret_key']
            
            print("  FOUND: trading.alpaca_api_key")
            print(f"  Key: {api_key[:8]}...{api_key[-8:]}")
            
            # Set as env vars
            os.environ['ALPACA_API_KEY'] = api_key
            os.environ['ALPACA_API_SECRET'] = api_secret
            
            print("\n  Set environment variables:")
            print(f"     ALPACA_API_KEY={api_key}")
            print(f"     ALPACA_API_SECRET={api_secret}")
            
            # STEP 2: Test the client
            print("\nTesting Universal API Client...")
            from universal_api import create_alpaca_client
            
            # Paper trading
            print("\n  Testing PAPER trading...")
            try:
                client = create_alpaca_client(paper=True)
                print(f"  Mode: {client.mode}")
                print(f"  Has creds: {client._has_creds()}")
                
                account = client.get_account()
                if account and isinstance(account, dict):
                    print("  SUCCESS!")
                    print(f"     Status: {account.get('status')}")
                    equity = account.get('equity', 0)
                    if equity:
                        print(f"     Equity: ${float(equity):,.2f}")
                    cash = account.get('cash', 0)
                    if cash:
                        print(f"     Cash: ${float(cash):,.2f}")
                    bp = account.get('buying_power', 0)
                    if bp:
                        print(f"     Buying Power: ${float(bp):,.2f}")
                else:
                    print(f"  Response: {str(account)[:200]}")
            except Exception as e:
                print(f"  Error: {e}")
            
            # Live trading
            print("\n  Testing LIVE trading...")
            try:
                client2 = create_alpaca_client(paper=False)
                print(f"  Mode: {client2.mode}")
                print(f"  Has creds: {client2._has_creds()}")
                
                account2 = client2.get_account()
                if account2 and isinstance(account2, dict):
                    print("  SUCCESS!")
                    print(f"     Status: {account2.get('status')}")
                    equity2 = account2.get('equity', 0)
                    if equity2:
                        print(f"     Equity: ${float(equity2):,.2f}")
                else:
                    print(f"  Response: {str(account2)[:200]}")
            except Exception as e:
                print(f"  Error: {e}")
                print(f"  Note: Live API may need network policy update")
                
        else:
            print("  No trading.alpaca_api_key in config.yaml")
            print("     Check: cat config.yaml | grep -A5 trading")
            
    except ImportError:
        print("  pyyaml not installed")
        print("     Fix: pip install pyyaml")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print(f"  config.yaml not found at {config_path}")
    print(f"     Check: ls -la /sandbox/new/config.yaml")

print("\n" + "=" * 60)
print("FIX COMPLETE")
print("=" * 60)
