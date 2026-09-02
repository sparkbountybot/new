#!/usr/bin/env python3
"""
Fix spark3 Alpaca connection — Set credentials + verify Live API access

Run on spark3 to diagnose and fix:
1. Check/set API credentials from .env or config.yaml
2. Verify Paper API works
3. Verify Live API access (may need network policy update)
"""
import subprocess, json, os, sys, socket, warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("ALPACA LIVE CONNECTION FIX — SPARK3")
print("=" * 70)

# STEP 1: Check for credentials
print("\n🔑 STEP 1: Finding API Credentials")
print("-" * 40)

# Check multiple sources for credentials
api_key = None
api_secret = None
creds_source = None

# Try env vars first
api_key = os.environ.get('ALPACA_API_KEY', '')
api_secret = os.environ.get('ALPACA_SECRET_KEY', '')

if api_key and api_secret:
    print(f"  ✅ From environment variables")
    creds_source = 'env'

# Try .env file
env_file = '.env'
if os.path.exists(env_file) and not api_key:
    print(f"  ✅ Found {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key == 'ALPACA_API_KEY' and not api_key:
                    api_key = value
                    creds_source = 'env_file'
                    print(f"     ALPACA_API_KEY = {value[:8]}...{value[-8:]}")
                elif key == 'ALPACA_SECRET_KEY' and not api_secret:
                    api_secret = value
                    creds_source = 'env_file'
                    print(f"     ALPACA_SECRET_KEY = {value[:8]}...{value[-8:]}")

# Try config.yaml
config_file = 'config.yaml'
if (not api_key or not api_secret) and os.path.exists(config_file):
    print(f"  ✅ Found {config_file}")
    try:
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f) or {}
        
        # Check various places for credentials
        trading = config.get('trading', {})
        alpaca = config.get('alpaca', {})
        trading_alpaca = trading.get('alpaca', {})
        
        if not api_key and trading_alpaca.get('api_key'):
            api_key = trading_alpaca['api_key']
            api_secret = trading_alpaca.get('secret_key', '')
            creds_source = 'config.yaml'
        elif not api_key and alpaca.get('api_key'):
            api_key = alpaca['api_key']
            api_secret = alpaca.get('secret_key', '')
            creds_source = 'config.yaml'
        elif not api_key and trading.get('alpaca_api_key'):
            api_key = trading['alpaca_api_key']
            api_secret = trading.get('alpaca_secret_key', '')
            creds_source = 'config.yaml'
            
    except ImportError:
        print(f"  ⚠️  pyyaml not installed")
        print(f"     Fix: pip install pyyaml")
    except Exception as e:
        print(f"  ❌ Error reading {config_file}: {e}")

# If still not set, try APCA env vars
if not api_key:
    api_key = os.environ.get('APCA_API_KEY_ID', '')
if not api_secret:
    api_secret = os.environ.get('APCA_API_SECRET_KEY', '')

# STEP 2: Report found credentials
print("\n🔑 STEP 2: Verify API Credentials")
print("-" * 40)

if api_key and api_secret:
    print(f"  ✅ API_KEY: {api_key[:8]}...{api_key[-8:]}")
    print(f"  ✅ API_SECRET: {api_secret[:8]}...{api_secret[-8:]}")
    print(f"  📍 Source: {creds_source}")
else:
    print(f"  ❌ NO CREDENTIALS FOUND!")
    print(f"     The user said they gave spark3 the live creds.")
    print(f"     FIX: Check where the user saved them:")
    print(f"     1. .env file")
    print(f"     2. config.yaml")
    print(f"     3. Environment variables in this shell")
    print(f"     4. Hidden in config somewhere else")
    print(f"     5. Check /sandbox/ for any .env or config files")

# STEP 3: Test Paper API
print("\n📡 STEP 3: Test Paper API")
print("-" * 40)

if api_key and api_secret:
    # Test with Python requests
    try:
        import requests
        r = requests.get(
            'https://paper-api.alpaca.markets/v2/account',
            headers={
                'APCA-API-KEY-ID': api_key,
                'APCA-API-SECRET-KEY': api_secret
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ Paper API: HTTP {r.status_code} — SUCCESS")
            print(f"     Status: {data.get('status')}")
            print(f"     Portfolio: ${float(data.get('portfolio_value', 0)):,.2f}")
            print(f"     Cash: ${float(data.get('cash', 0)):,.2f}")
            print(f"     Buying Power: ${float(data.get('buying_power', 0)):,.2f}")
        elif r.status_code == 401:
            print(f"  ❌ Paper API: HTTP {r.status_code} — AUTH FAILED")
            print(f"     Check credentials!")
        else:
            print(f"  ❌ Paper API: HTTP {r.status_code} — {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Paper API: {str(e)[:50]}")

# STEP 4: Test Live API
print("\n📡 STEP 4: Test Live API")
print("-" * 40)

if api_key and api_secret:
    # Test with curl (more reliable than requests)
    try:
        cmd = (
            f'curl -s --max-time 10 '
            f'"https://api.alpaca.markets/v2/account" '
            f'-H "APCA-API-KEY-ID: {api_key}" '
            f'-H "APCA-API-SECRET-KEY: {api_secret}"'
        )
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if 'status' in data:
                    print(f"  ✅ Live API: HTTP 200 — SUCCESS")
                    print(f"     Status: {data.get('status')}")
                    print(f"     Portfolio: ${float(data.get('portfolio_value', 0)):,.2f}")
                    print(f"     Cash: ${float(data.get('cash', 0)):,.2f}")
                    print(f"     Buying Power: ${float(data.get('buying_power', 0)):,.2f}")
                else:
                    print(f"  ✅ Live API: {result.stdout[:100]}")
            except json.JSONDecodeError:
                print(f"  ✅ Live API returned: {result.stdout[:100]}")
        else:
            print(f"  ❌ Live API: curl failed (code {result.returncode})")
            print(f"     stderr: {result.stderr[:100]}")
            print(f"     FIX: May need to update network policy")
            print(f"     Run on host: openshell policy update spark3 --add-endpoint api.alpaca.markets:443:read-write:rest:enforce --wait")
    except Exception as e:
        print(f"  ❌ Live API: {str(e)[:50]}")

# STEP 5: Check DNS
print("\n🌐 STEP 5: DNS Check")
print("-" * 40)

dns_tests = ['paper-api.alpaca.markets', 'api.alpaca.markets']
for host in dns_tests:
    try:
        ips = socket.gethostbyname(host)
        print(f"  ✅ {host} -> {ips}")
    except:
        # Try DoH
        try:
            cmd = f'curl -s --max-time 5 "https://dns.google/resolve?name={host}&type=A"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0 and 'answer' in result.stdout:
                data = json.loads(result.stdout)
                for ans in data.get('answer', []):
                    print(f"  ✅ {host} -> {ans['data']} (via DoH)")
            else:
                print(f"  ❌ {host} -> DNS FAILED")
        except:
            print(f"  ❌ {host} -> DNS FAILED")

# STEP 6: Provide fix recommendations
print("\n" + "=" * 70)
print("FIX RECOMMENDATIONS")
print("=" * 70)

if api_key and api_secret:
    print("\n✅ CREDENTIALS FOUND!")
    print("\n📝 Next steps:")
    print("   1. If Paper API works but Live API doesn't:")
    print("      Run on HOST machine:")
    print("      openshell policy update spark3 \\")
    print("        --add-endpoint api.alpaca.markets:443:read-write:rest:enforce \\")
    print("        --wait")
    print("")
    print("   2. If neither API works:")
    print("      Check where credentials were saved")
    print("      Look in: .env, config.yaml, environment variables")
    print("")
    print("   3. Run this diagnostic again after fix:")
    print("      python3 diagnose_alpaca.py")
else:
    print("\n❌ CREDENTIALS NOT FOUND!")
    print("\n📝 Fix: Set environment variables")
    print("   export ALPACA_API_KEY='your_key'")
    print("   export ALPACA_SECRET_KEY='your_secret'")
    print("")
    print("   Or create .env file:")
    print("   echo 'ALPACA_API_KEY=your_key' > .env")
    print("   echo 'ALPACA_SECRET_KEY=your_secret' >> .env")
    print("")
    print("   Then reload:")
    print("   source .env")
    print("   python3 diagnose_alpaca.py")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
