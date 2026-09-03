# Policy Fix — Python SDK access to data.alpaca.markets
**Created: 2026-09-03 15:45 UTC**

## Problem
- ✅ curl works to data.alpaca.markets (v32/v33 policy)
- ❌ Python requests/SDK still blocked (403 tunnel)
- The --binary argument only accepted the first path, not all binaries
- Python venv uses: /sandbox/new/.venv/bin/python3
- System curl: /usr/bin/curl

## Fix — Add all binary paths
Run on host, ONE LINE at a time:

### Step 1: Remove data.alpaca.markets from policy
```
openshell policy update spark3 --remove-endpoint data.alpaca.markets:443 --wait
```

### Step 2: Add back with correct binary paths (one at a time)
```
openshell policy update spark3 --add-endpoint data.alpaca.markets:443:read-write:rest:enforce --binary /usr/bin/curl --wait
```

```
openshell policy update spark3 --add-endpoint /usr/bin/python3 --wait
```

```
openshell policy update spark3 --add-endpoint /usr/bin/python3.13 --wait
```

```
openshell policy update spark3 --add-endpoint /sandbox/new/.venv/bin/python3 --wait
```

```
openshell policy update spark3 --add-endpoint /usr/local/bin/python3 --wait
```

```
openshell policy update spark3 --add-endpoint /usr/local/bin/python3.13 --wait
```

### Step 3: Verify policy
```
openshell policy get spark3
```

### Step 4: Test from this sandbox
```
cd /sandbox/new && source .venv/bin/activate && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'AKESB677ODE3GUAVWU24W4647X', 'APCA-API-SECRET-KEY': '8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.get('https://data.alpaca.markets/v1beta3/crypto/us/bars?start=2026-09-01&end=2026-09-03&timeframe=1Day&symbols=BTC%2FUSD', headers=hdrs, timeout=10)
print(f'Status: {r.status_code}')
print(r.text[:200])
"
```

## NOTE
The --binary flag may only accept ONE binary at a time. If so, we need to submit one policy update per binary path.

## PYTHON PATHS TO ALLOW
- /usr/bin/curl (system curl)
- /usr/bin/python3 (system Python)
- /usr/bin/python3.13 (system Python)
- /sbin/new/.venv/bin/python3 (venv Python — THIS is the one we need!)
- /usr/local/bin/python3 (if exists)
- /usr/local/bin/python3.13 (if exists)
