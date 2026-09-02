# Rebuild Instructions for BountyBot Sandbox

## When to Rebuild
- Sandbox lost all network access (even curl)
- Policy version corrupted or unreachable
- After major OpenShell/NemoClaw updates
- Manual sandbox restart fails

## Quick Rebuild Process

### Step 1: Destroy and recreate sandbox
```bash
# List all sandboxes
openshell sandbox list

# Delete the broken sandbox
openshell sandbox delete spark2

# Recreate it
openshell sandbox create spark2
```

### Step 2: Wait for it to be ready
```bash
# Check status repeatedly until "Ready"
openshell sandbox list
# Wait until spark2 shows "Ready" status
```

### Step 3: Apply network policy
```bash
# DNS resolution endpoint
openshell policy update spark2 \
  --add-endpoint dns.google:443:read-write:rest:enforce \
  --add-allow dns.google:443:GET:/resolve** \
  --binary /usr/bin/python3 \
  --binary /usr/local/bin/python3 \
  --binary /usr/bin/curl \
  --binary /usr/local/bin/curl \
  --wait

# Alpaca API endpoints (paper + live)
openshell policy update spark2 \
  --add-endpoint paper-api.alpaca.markets:443:read-write:rest:enforce \
  --add-endpoint api.alpaca.markets:443:read-write:rest:enforce \
  --add-endpoint 35.194.67.18:443:read-write:rest:enforce \
  --binary /usr/bin/python3 \
  --binary /usr/local/bin/python3 \
  --binary /usr/bin/curl \
  --binary /usr/local/bin/curl \
  --wait
```

### Step 4: Clone repo and install
```bash
# SSH into sandbox
openshell sandbox connect spark2

# Clone and setup
cd /sandbox
git clone https://sparkbountybot:<PAT>@github.com/sparkbountybot/bountybot-framework-v2.git
cd bountybot-framework-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Test connectivity
```bash
# Test DNS
curl -s "https://dns.google/resolve?name=paper-api.alpaca.markets&type=A"

# Test API
curl -s -H "APCA-API-KEY-ID: YOUR_KEY" -H "APCA-API-SECRET-KEY: YOUR_SECRET" \
  "https://paper-api.alpaca.markets/v2/account"
```

## Time Estimate
- Steps 1-3: ~2-3 minutes
- Step 4: ~3-5 minutes (git clone + pip install)
- Step 5: ~30 seconds
- Total: ~6-8 minutes

## Alternative: Fix without rebuild
If sandbox is still accessible, try:
```bash
# Restart sandbox first
openshell sandbox restart spark2

# Reapply policy
openshell policy update spark2 --add-endpoint dns.google:443:read-write:rest:enforce \
  --add-allow dns.google:443:GET:/resolve** --wait

openshell policy update spark2 --add-endpoint paper-api.alpaca.markets:443:read-write:rest:enforce \
  --add-endpoint 35.194.67.18:443:read-write:rest:enforce --wait
```

## If curl still fails after rebuild
This means the policy didn't apply. Check:
```bash
openshell policy get spark3 2>&1
# Should show "Version" and "Effective" status
```

If version doesn't update, try:
```bash
openshell policy update spark2 --policy /dev/null --wait
# Force policy refresh, then reapply endpoints
```
