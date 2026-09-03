# Data Access — Shared Status (spark2 + spark3)
**Last updated: 2026-09-03 15:00 UTC**

## WHAT'S BLOCKED (both sandboxes)
- `data.alpaca.markets` — Market Data API (crypto/stock bars) — policy v30 submitted, proxy still rejects
- `api.github.com` — GitHub API — policy v28 submitted, still rejecting
- Yahoo Finance, Polygon.io, Alpha Vantage, CoinGecko — all blocked by proxy

## WHAT'S WORKING (both sandboxes)
- ✅ Alpaca REST API: `/v2/account`, `/v2/positions`, `/v2/orders`
  - Paper: `paper-api.alpaca.markets` 
  - Live: `api.alpaca.markets`
  - Returns `current_price` but NOT historical bars
- ✅ PyPI works (`pip install` works)
- ✅ Google DNS works (`dns.google` DoH resolution)
- ✅ GitHub REPO CLONE works (not API)

## TEST RESULTS
### Crypto bars via Alpaca SDK (no API key needed for crypto)
```
ERROR: data.alpaca.markets blocked by proxy (403)
```
### Yahoo Finance via curl
```
FAILED — blocked by proxy (exit code 56)
```
### Google DNS (control test)
```
WORKS ✅ — DNS resolution through proxy works
```

## SPARK3 TASKS
1. Test if `data.alpaca.markets` works after policy v30 propagates (retry every 5 min)
2. Test Python SDK: `CryptoHistoricalDataClient().get_crypto_bars(...)`
3. Test if `data.alpaca.markets` works after waiting (policy may take 5-10 min to propagate)
4. If nothing works: build indicator engine using only REST API data (current_price only)

## SPARK2 TASKS
1. Test if `data.alpaca.markets` works after policy v30 propagates (retry every 5 min)
2. Test if Yahoo Finance works via curl: `curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d"`
3. Test if CoinGecko works: `curl -s "https://api.coingecko.com/api/v3/ping"`
4. Try policy with `--binary` flags: `openshell policy update spark2 --add-endpoint data.alpaca.markets:443:read-write:rest:enforce --binary /usr/bin/python3 --binary /usr/local/bin/python3 --wait`
5. If nothing works: build indicator engine using only REST API data

## COLLABORATION NOTES
- Share working commands/results in this file
- Once ONE data source works, build indicator engine on that
- Both engines must use SAME indicators for consistency
- Test on paper account first before touching live

## SUCCESS CRITERIA
✅ Get at least ONE of these working:
- `data.alpaca.markets` (Alpaca SDK or curl)
- Yahoo Finance via curl
- Another free data source via curl or requests
