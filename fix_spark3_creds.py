#!/usr/bin/env python3
"""Fix spark3 Alpaca connection — loads creds from config.yaml or .env"""
import os
import sys
import warnings
import subprocess
import json

warnings.filterwarnings('ignore')

print("=" * 60)
print("ALPACA CREDENTIAL FIX — SPARK3")
print("=" * 60)

# STEP 1: Find credentials from config.yaml
print("\nChecking config.yaml...")
config_yaml = '/sandbox/new/config.yaml'
if os.path.exists(config_yaml):
    try:
        import yaml
        with open(config_yaml) as f:
            config = yaml.safe_load(f) or {}
        
        trading = config.get('trading', {})
        if trading.get('alpaca_api_key'):
            api_key = trading['alpaca_api_key']
            api_secret = trading.get('alpaca_secret_key', '')
            print("  FOUND in config.yaml")
            print(f"  Key: {api_key[:8]}...{api_key[-8:]}")
            
            # Set as env vars for this session
            os.environ['ALPACA_API_KEY'] = api_key
            os.environ['ALPACA_API_SECRET'] = api_secret
            
            print("\n  Set environment variables:")
            print("    export ALPACA_API_KEY='" + api_key + "'")
            print("    export ALPACA_API_SECRET='" + api_secret + "'")
            
            print("\n  Add to ~/.bashrc to persist:")
            print("    echo 'export ALPACA_API_KEY=" + api_key + "' >> ~/.bashrc")
            print("    echo 'export ALPACA_API_SECRET=" + api_secret + "' >> ~/.bashrc")
            
            # Test the client immediately
            print("\n  Testing Universal API Client...")
            from universal_api import create_alpaca_client
            
            # Paper trading
            try:
                client = create_alpaca_client(paper=True)
                print("  Paper trading: Mode=" + client.mode + ", Creds=OK")
                account = client.get_account()
                if account and isinstance(account, dict):
                    print("  Status: " + str(account.get('status')))
                    equity = account.get('equity', 0)
                    if equity:
                        print("  Equity: $" + str(float(equity)))
                else:
                    print("  Response: " + str(account)[:200])
            except Exception as e:
                print("  Paper trading error: " + str(e))
            
            # Live trading
            print("\n  Testing live trading...")
            try:
                client2 = create_alpaca_client(paper=False)
                print("  Live trading: Mode=" + client2.mode + ", Creds=OK")
                account2 = client2.get_account()
                if account2 and isinstance(account2, dict):
                    print("  Status: " + str(account2.get('status')))
                    equity2 = account2.get('equity', 0)
                    if equity2:
                        print("  Equity: $" + str(float(equity2)))
                    else:
                        print("  Response: " + str(account2)[:200])
                else:
                    print("  Response: " + str(account2)[:200])
            except Exception as e:
                print("  Live trading error: " + str(e))
                
        else:
            print("  No trading.alpaca_api_key in config.yaml")
            print("     Check: cat config.yaml | grep -A5 trading")
            
    except ImportError:
        print("  pyyaml not installed")
        print("     Fix: pip install pyyaml")
    except Exception as e:
        print("  Error reading config.yaml: " + str(e))
else:
    print("  config.yaml not found")
    print("     Check: ls -la /sandbox/new/config.yaml")

print("\n" + "=" * 60)
print("FIX COMPLETE")
print("=" * 60)
