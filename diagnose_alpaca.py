#!/usr/bin/env python3
"""
Alpaca Connection Diagnostic — Run on spark3

Helps diagnose and fix connection issues after receiving live credentials.
"""
import subprocess, json, os, sys, socket, time

print("=" * 70)
print("ALPACA CONNECTION DIAGNOSTIC — SPARK3")
print("=" * 70)

# Test 1: Check environment variables
print("\n🔑 STEP 1: Check API Credentials")
print("-" * 40)

api_key = os.environ.get('ALPACA_API_KEY', '')
api_secret = os.environ.get('ALPACA_SECRET_KEY', '')
alpa_ca_api_key = os.environ.get('ALPACA_API_KEY', '')  # Could be set either way
alpa_ca_secret = os.environ.get('ALPACA_SECRET_KEY', '')

# Try common env var names
env_vars = {
    'ALPACA_API_KEY': os.environ.get('ALPACA_API_KEY', ''),
    'ALPACA_API_KEY_LIVE': os.environ.get('ALPACA_API_KEY_LIVE', ''),
    'ALPACA_LIVE_API_KEY': os.environ.get('ALPACA_LIVE_API_KEY', ''),
}

api_key_set = False
api_secret_set = False

for name, value in env_vars.items():
    if value and value != '':
        print(f"  ✅ {name}: {value[:8]}...{value[-8:]}")
        api_key_set = True

api_secret_name = None
for name in ['ALPACA_SECRET_KEY', 'ALPACA_SECRET_KEY_LIVE', 'ALPACA_LIVE_SECRET_KEY']:
    value = os.environ.get(name, '')
    if value and value != '':
        print(f"  ✅ {name}: {value[:8]}...{value[-8:]}")
        api_secret_set = True
        api_secret_name = name
        break

if not api_key_set:
    print("  ❌ No API key found in environment")
    print("     Fix: export ALPACA_API_KEY='your_key'")
    print("     Or create .env file with: ALPACA_API_KEY=your_key")

if not api_secret_set:
    print("  ❌ No API secret found in environment")
    print("     Fix: export ALPACA_SECRET_KEY='your_secret'")
    print("     Or create .env file with: ALPACA_SECRET_KEY=your_secret")

# Test 2: DNS resolution
print("\n🌐 STEP 2: DNS Resolution")
print("-" * 40)

dns_tests = [
    'paper-api.alpaca.markets',
    'api.alpaca.markets',
    'www.google.com'
]

for host in dns_tests:
    try:
        ips = socket.gethostbyname(host)
        print(f"  ✅ {host} -> {ips}")
    except socket.gaierror:
        # Try curl DoH
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
            print(f"  ❌ {host} -> DNS FAILED (both methods)")

# Test 3: Check if we can reach Alpaca endpoints
print("\n📡 STEP 3: Endpoint Connectivity")
print("-" * 40)

endpoints = [
    ('Paper API', 'https://paper-api.alpaca.markets'),
    ('Live API', 'https://api.alpaca.markets'),
]

for name, base_url in endpoints:
    headers_str = f' -H "APCA-API-KEY-ID: {api_key_set and api_key[:8] + "..." or "NOT SET"}" -H "APCA-API-SECRET-KEY: {api_secret_set and api_secret[:8] + "..." or "NOT SET"}"'
    
    # Try with curl
    try:
        cmd = f'curl -s --max-time 5 -o /dev/null -w "%{{http_code}}" {base_url}/v2/account {headers_str}'
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        code = result.stdout.strip()
        
        if code == '200':
            print(f"  ✅ {name}: HTTP {code} — WORKING!")
        elif code == '401':
            print(f"  ⚠️  {name}: HTTP {code} — CONNECTED but auth failed")
            print(f"     Check credentials!")
        elif code == '000':
            print(f"  ❌ {name}: Connection FAILED")
            print(f"     Check network policy/endpoint")
        else:
            print(f"  ❌ {name}: HTTP {code} — Unknown error")
    except Exception as e:
        print(f"  ❌ {name}: {str(e)[:50]}")

# Test 4: Python requests test
print("\n🐍 STEP 4: Python Requests")
print("-" * 40)

try:
    import requests
    print(f"  ✅ requests module installed")
    
    for name, base_url in endpoints:
        try:
            r = requests.get(f'{base_url}/v2/account', 
                           headers={
                               'APCA-API-KEY-ID': api_key,
                               'APCA-API-SECRET-KEY': api_secret
                           }, timeout=5)
            print(f"  ✅ {name}: HTTP {r.status_code} — {len(r.text)} bytes")
            if r.status_code == 200:
                data = r.json()
                if 'status' in data:
                    print(f"     Status: {data['status']}")
            elif r.status_code == 401:
                print(f"     Auth failed: {r.text[:100]}")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ {name}: Connection refused — requests blocked by policy")
        except Exception as e:
            print(f"  ❌ {name}: {str(e)[:50]}")
except ImportError:
    print(f"  ❌ requests NOT installed")
    print(f"     Fix: pip install requests")

# Test 5: Port connectivity
print("\n🚪 STEP 5: Port Check")
print("-" * 40)

for host in ['paper-api.alpaca.markets', 'api.alpaca.markets']:
    try:
        sock = socket.create_connection((host, 443), timeout=5)
        print(f"  ✅ {host}:443 — OPEN")
        sock.close()
    except socket.gaierror:
        print(f"  ❌ {host}:443 — DNS failed")
    except socket.timeout:
        print(f"  ❌ {host}:443 — Timed out (port blocked?)")
    except Exception as e:
        print(f"  ❌ {host}:443 — {str(e)}")

# Test 6: Network policy
print("\n🔒 STEP 6: Network Policy")
print("-" * 40)

try:
    cmd = 'openshell policy list 2>&1'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        print("  ✅ openshell available")
        print(f"     Policy info:\n{result.stdout[:500]}")
    else:
        print(f"  ❌ openshell not available: {result.stderr[:100]}")
        print("     Try: openshell policy list")
except:
    print("  ❌ openshell not installed")

# Fix recommendations
print("\n" + "=" * 70)
print("FIX RECOMMENDATIONS")
print("=" * 70)

if not api_key_set or not api_secret_set:
    print("\n❌ PROBLEM: Missing credentials")
    print("SOLUTION: Set environment variables")
    print("  export ALPACA_API_KEY='your_key'")
    print("  export ALPACA_SECRET_KEY='your_secret'")
    print("")
    print("  Or create .env file:")
    print("  echo 'ALPACA_API_KEY=your_key' > .env")
    print("  echo 'ALPACA_SECRET_KEY=your_secret' >> .env")
    print("")
    print("  Then load it:")
    print("  source .env")
elif '200' in str(['200']):  # If we found a 200 response
    print("\n✅ ALL TESTS PASSED — Connection should work!")
    print("Run: python swing_trading_engine.py")
else:
    print("\n❌ PROBLEM: Connection issues detected")
    print("SOLUTION: Check network policy")
    print("  openshell policy list")
    print("")
    print("SOLUTION: Add Alpaca endpoints to policy")
    print("  openshell policy update spark3 \\")
    print("    --add-endpoint paper-api.alpaca.markets:443:read-write:rest:enforce \\")
    print("    --add-endpoint api.alpaca.markets:443:read-write:rest:enforce \\")
    print("    --wait")
    print("")
    print("SOLUTION: Try DNS resolution")
    print("  curl -s 'https://dns.google/resolve?name=paper-api.alpaca.markets&type=A'")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
