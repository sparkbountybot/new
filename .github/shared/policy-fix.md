# Policy Status Check
**Run this on the host**

## Step 1: Check current policy state
```
openshell policy status spark3
```

## Step 2: Check what endpoints are actually configured
```
openshell policy show spark3 2>/dev/null
```
or
```
openshell policy list spark3 2>/dev/null
```

## Step 3: Check if data.alpaca.markets is already in policy (blocked)
```
openshell policy show spark3 2>/dev/null | grep -i alpaca
openshell policy show spark3 2>/dev/null | grep -i data
```

## Step 4: Try removing and re-adding
```
# Remove first
openshell policy update spark3 --remove-endpoint data.alpaca.markets:443:rest:enforce --wait
# Then add back
openshell policy update spark3 --add-endpoint data.alpaca.markets:443:read-write:rest:enforce --wait
```

## Step 5: Try different syntax
The proxy may need explicit paths or methods:
```
openshell policy update spark3 --add-endpoint data.alpaca.markets:443:read:rest:enforce --wait
openshell policy update spark3 --add-endpoint data.alpaca.markets:443:read-write:https:enforce --wait
openshell policy update spark3 --add-endpoint data.alpaca.markets:443:tunnel:enforce --wait
```

## Step 6: Check if there's a blanket block
```
openshell policy show spark3 2>/dev/null | grep -i block
openshell policy show spark3 2>/dev/null | grep -i deny
```
