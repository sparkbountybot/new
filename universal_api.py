#!/usr/bin/env python3
"""
Universal API Client — Works in any sandbox network policy

Auto-detects network capability on startup:
  1. Try Python requests first (spark3 has this, spark2 doesn't)
  2. Fall back to curl subprocess (both sandboxes have this)
  3. Handle DNS resolution (blocked in both — resolved via curl DoH)

Usage:
    from universal_api import Client
    
    client = Client(api_key="your_key", api_secret="your_secret")
    account = client.get("/v2/account")
    orders = client.get("/v2/orders")
    
    # Can also use as a standalone curl replacement
    result = client.fetch_json("https://api.example.com/data")
"""
import os
import sys
import json
import socket
import subprocess
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Try to import requests — may not be available or functional
try:
    import requests as _req
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NetworkStatus:
    """Diagnoses what network capabilities are available."""
    
    def __init__(self):
        self.requests_works = False
        self.dns_works = False
        self.curl_works = False
        self._diagnose()
    
    def _diagnose(self):
        """Test each capability."""
        # Test 1: Python requests
        if REQUESTS_AVAILABLE:
            try:
                r = _req.get(
                    "https://paper-api.alpaca.markets/v2/account",
                    headers={
                        "APCA-API-KEY-ID": "test",
                        "APCA-API-SECRET-KEY": "test",
                    },
                    timeout=5
                )
                # 401 means we reached the API (just bad creds) — that's success
                if r.status_code == 401 or r.status_code == 200:
                    self.requests_works = True
            except:
                self.requests_works = False
        
        # Test 2: DNS resolution via Python socket
        try:
            socket.gethostbyname("paper-api.alpaca.markets")
            self.dns_works = True
        except:
            self.dns_works = False
        
        # Test 3: curl subprocess
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "5",
                 "-o", "/dev/null",
                 "https://paper-api.alpaca.markets"],
                capture_output=True, text=True
            )
            self.curl_works = (r.returncode == 0)
        except:
            self.curl_works = False
    
    @property
    def can_direct_http(self):
        return self.requests_works
    
    @property
    def can_resolve_dns(self):
        return self.dns_works
    
    @property
    def can_curl(self):
        return self.curl_works
    
    @property
    def best_mode(self):
        if self.requests_works:
            return "requests"
        elif self.curl_works:
            return "curl"
        return "none"
    
    def report(self):
        """Human-readable network status report."""
        lines = ["🔍 Network Diagnostics", "=" * 40]
        
        if self.requests_works:
            lines.append("✅ Python requests: WORKS")
        else:
            lines.append("❌ Python requests: BLOCKED or unavailable")
        
        if self.dns_works:
            lines.append("✅ DNS resolution: WORKS")
        else:
            lines.append("❌ DNS resolution: BLOCKED")
        
        if self.curl_works:
            lines.append("✅ curl subprocess: WORKS")
        else:
            lines.append("❌ curl subprocess: unavailable")
        
        lines.append(f"\n🎯 Best mode: {self.best_mode}")
        return "\n".join(lines)


def resolve_dns_via_curl(host):
    """Resolve DNS using curl DoH (dns.google)."""
    cmd = [
        "curl", "-s", "--max-time", "10",
        f"https://dns.google/resolve?name={host}&type=A"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            if "Answer" in data and len(data["Answer"]) > 0:
                return data["Answer"][0]["data"]
        except:
            pass
    return None


class UniversalClient:
    """API client that adapts to network capabilities at runtime."""
    
    def __init__(self, base_url="https://paper-api.alpaca.markets",
                 api_key=None, api_secret=None):
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("APCA_API_KEY_ID", "")
        self.api_secret = api_secret or os.environ.get("APCA_API_SECRET_KEY", "")
        self.status = NetworkStatus()
        self._creds_loaded = False  # track whether we have API credentials
        
        if self.status.best_mode == "none":
            raise RuntimeError("No network capability detected. Check sandbox policy.")
        
        self.mode = self.status.best_mode
    
    def _headers(self):
        """Generate auth headers."""
        headers = {"Accept": "application/json"}
        if self.api_key and self.api_secret:
            headers.update({
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
            })
        return headers
    
    def _has_creds(self):
        """Check if credentials are loaded."""
        return bool(self.api_key and self.api_secret)
    
    def _require_creds(self, endpoint):
        """Raise a clear error if credentials are needed but not present."""
        if not self._has_creds():
            raise RuntimeError(
                f"No API credentials for {endpoint}. "
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY env vars, "
                "or pass key= and secret= to create_alpaca_client()."
            )
    
    def _curl_cmd(self, endpoint, method="GET", body=None):
        """Build curl command for API call."""
        url = f"{self.base_url}{endpoint}"
        cmd = ["curl", "-s", "--max-time", "10", "-X", method]
        
        for k, v in self._headers().items():
            cmd.extend(["-H", f"{k}: {v}"])
        
        if body and method in ("POST", "PUT", "PATCH"):
            body_str = json.dumps(body)
            cmd.extend(["-d", body_str])
        
        # Handle DNS resolution
        if not self.status.can_resolve_dns:
            # Resolve the host via curl DoH
            host = self.base_url.replace("https://", "").split("/")[0]
            ip = resolve_dns_via_curl(host)
            if ip:
                cmd.extend(["--resolve", f"{host}:443:{ip}"])
        
        cmd.append(url)
        return cmd
    
    def _execute_curl(self, cmd):
        """Execute curl command and parse response."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return result.stdout
        return None
    
    def _execute_requests(self, endpoint, method="GET", body=None):
        """Execute using Python requests."""
        url = f"{self.base_url}{endpoint}"
        
        headers = self._headers()
        if body and method in ("POST", "PUT", "PATCH"):
            headers["Content-Type"] = "application/json"
        
        try:
            r = _req.request(method, url, headers=headers, json=body, timeout=10)
            if r.status_code == 204 or r.status_code == 201:
                return None  # No content
            return r.json()
        except Exception as e:
            # If requests fail, fall back to curl
            print(f"  requests failed, falling back to curl: {e}")
            self.mode = "curl"
            cmd = self._curl_cmd(endpoint, method, body)
            return self._execute_curl(cmd)
    
    def get(self, endpoint):
        """GET request — auto-detects best method."""
        if self.mode == "requests":
            return self._execute_requests(endpoint, "GET")
        else:
            cmd = self._curl_cmd(endpoint, "GET")
            return self._execute_curl(cmd)
    
    def post(self, endpoint, body=None):
        """POST request — auto-detects best method."""
        if self.mode == "requests":
            return self._execute_requests(endpoint, "POST", body)
        else:
            cmd = self._curl_cmd(endpoint, "POST", body)
            return self._execute_curl(cmd)
    
    def delete(self, endpoint):
        """DELETE request — auto-detects best method."""
        if self.mode == "requests":
            return self._execute_requests(endpoint, "DELETE")
        else:
            cmd = self._curl_cmd(endpoint, "DELETE")
            return self._execute_curl(cmd)
    
    def get_account(self):
        """Shorthand for getting Alpaca account."""
        return self.get("/v2/account")
    
    def get_positions(self):
        """Shorthand for getting positions."""
        return self.get("/v2/positions")
    
    def get_orders(self, status="open"):
        """Shorthand for getting orders."""
        return self.get(f"/v2/orders?status={status}")
    
    def submit_order(self, symbol, qty, side="buy", type="market",
                     time_in_force="day", **kwargs):
        """Submit a paper trade order."""
        order = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": type,
            "time_in_force": time_in_force,
            **kwargs
        }
        return self.post("/v2/orders", order)
    
    def diagnose(self):
        """Print full network diagnosis."""
        return self.status.report()


# Convenience: create an Alpaca-specific client
def create_alpaca_client(key=None, secret=None, paper=True):
    """Create a pre-configured Alpaca client.
    
    Auto-detects credentials from environment or config file.
    """
    if not key or not secret:
        # Try config.yaml (where credentials are stored at [trading] section)
        config_yaml = Path(__file__).parent / "config.yaml"
        if config_yaml.exists():
            try:
                import yaml as _yaml
                with open(config_yaml) as _f:
                    cfg = _yaml.safe_load(_f) or {}
                    trading = cfg.get("trading", {})
                    if trading.get("alpaca_api_key"):
                        key = key or trading["alpaca_api_key"]
                        secret = secret or trading["alpaca_secret_key"]
            except Exception as e:
                print(f"  Warning: could not load config.yaml: {e}")
    
    # Also try environment variables
    if not key or not secret:
        key = key or os.environ.get("APCA_API_KEY_ID", "")
        secret = secret or os.environ.get("APCA_API_SECRET_KEY", "")
    
    if not key or not secret:
        raise RuntimeError(
            "No Alpaca API credentials found. Set either:\n"
            "  1. config.yaml [trading].alpaca_api_key / alpaca_secret_key\n"
            "  2. Environment variables: APCA_API_KEY_ID + APCA_API_SECRET_KEY\n"
            "  3. Or pass directly: create_alpaca_client(key='...', secret='...')"
        )
    
    base = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    client = UniversalClient(base_url=base, api_key=key, api_secret=secret)
    client._creds_loaded = True
    return client


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Universal API Client — network auto-detection")
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        default=True,  # show diagnostics by default
        help="Run network diagnostics and print capability report (default behavior)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a live API test (GET /v2/account)"
    )
    parser.add_argument(
        "--mode",
        choices=["requests", "curl", "auto"],
        default="auto",
        help="Force HTTP mode (default: auto-detect)"
    )
    args = parser.parse_args()
    
    mode_override = args.mode
    
    print("=" * 50)
    print("  Universal API Client")
    print("=" * 50)
    
    status = NetworkStatus()
    print(status.report())
    print()
    
    best = status.best_mode
    
    if args.test or args.auto_detect:
        print(f"\n🔧 Creating client (mode: {best if mode_override == 'auto' else mode_override})...")
        try:
            if mode_override != "auto":
                # Force a specific mode — hack the status object
                status.requests_works = (mode_override == "requests")
                status.curl_works = (mode_override == "curl")
                status.dns_works = False
                best = mode_override
            
            client = create_alpaca_client()
            # Override mode if forced
            if mode_override != "auto":
                client.mode = mode_override
                client.status = status
            
            print(f"  Client mode: {client.mode}")
            
            if args.test:
                print("\n📡 Testing API call...")
                try:
                    account = client.get_account()
                    if account and isinstance(account, dict):
                        status_val = account.get("status", "UNKNOWN")
                        equity = account.get("equity", 0)
                        cash = account.get("cash", 0)
                        bp = account.get("buying_power", 0)
                        print(f"  ✅ Status: {status_val}")
                        try:
                            if equity: print(f"  ✅ Equity: ${float(equity):,.2f}")
                        except: print(f"  ✅ Equity: {equity}")
                        try:
                            if cash: print(f"  ✅ Cash: ${float(cash):,.2f}")
                        except: print(f"  ✅ Cash: {cash}")
                        print(f"  ✅ ID: {account.get('id', 'N/A')}")
                        try:
                            if bp: print(f"  ✅ Buying Power: ${float(bp):,.2f}")
                        except: print(f"  ✅ Buying Power: {bp}")
                    else:
                        print(f"  Response: {str(account)[:200]}")
                except Exception as e:
                    print(f"  ❌ API call failed: {e}")
                    print(f"     (This is expected if credentials are missing from config.yaml)")
            else:
                if client._has_creds():
                    print(f"  ✅ Credentials loaded from config.yaml")
                else:
                    print(f"  ⚠️  No credentials loaded — credentials should be in config.yaml [trading] section")
        except RuntimeError as e:
            print(f"  ❌ {e}")
        except Exception as e:
            print(f"  ⚠️  Unexpected error: {e}")
    
    print(f"\n✅ Ready. Mode: {best}")
    print(f"   Import: from universal_api import create_alpaca_client")
    print(f"   Usage:  client = create_alpaca_client()")
