"""BountyBot Manager - CLI."""
import sys, os, json, yaml
from datetime import datetime

def load_config(path="config.yaml"):
    defaults = {
        "github": {"org": "sparkbountybot", "watch_interval_seconds": 300},
        "gmail": {"email": "", "password": "", "check_interval_seconds": 300},
        "trading": {
            "alpaca_api_key": "", "alpaca_secret_key": "",
            "base_url": "https://paper-api.alpaca.markets",
            "paper": True, "max_position_pct": 0.3,
            "max_total_risk": 0.05,
        },
        "email": {"from": "bountybot@sparkbountybot.com"},
        "sendgrid": {"api_key": ""},
    }
    try:
        with open(path) as f:
            uc = yaml.safe_load(f) or {}
            for k in defaults:
                if k in uc and isinstance(defaults[k], dict):
                    defaults[k].update(uc[k])
                elif k in uc:
                    defaults[k] = uc[k]
    except FileNotFoundError:
        print(f"Warning: {path} not found")
    except Exception as e:
        print(f"Warning: {e}")
    return defaults

def cmd_status(config):
    try:
        from bounty_scanner import BountyScanner
        s = BountyScanner(config).get_summary()
        print("\nGitHub Scanner:")
        print(f"  Total: {s.get('total', 0)} "
              f"Critical: {s.get('critical', 0)} "
              f"High: {s.get('high', 0)} "
              f"Medium: {s.get('medium', 0)} "
              f"Reward: ${s.get('total_reward', 0)}")
    except Exception as e:
        print(f"\nGitHub Scanner: Error - {e}")
    try:
        from trader import Trader
        p = Trader(config).get_portfolio()
        print("\nPaper Trader:")
        print(f"  Cash: ${p.get('cash', 0):.2f} "
              f"Equity: ${p.get('equity', 0):.2f} "
              f"P&L: ${p.get('pnl', 0):.2f}")
        print(f"  Positions: {len(p.get('positions', {}))}")
    except Exception as e:
        print(f"\nPaper Trader: Error - {e}")
    ec = config.get("gmail", {})
    if ec.get("email") and ec.get("password"):
        print("\nGmail Monitor: OK")
    else:
        print("\nGmail Monitor: Not configured")

def cmd_query(config):
    try:
        from bounty_scanner import BountyScanner
        a = BountyScanner(config).get_alerts()
        if not a:
            print("No alerts")
            return
        for i, x in enumerate(a[-10:], 1):
            print(f"{i}. [{x.get('difficulty', '?').upper()}] "
                  f"${x.get('reward', 0):>5} - "
                  f"{x.get('repo', '?')}: "
                  f"{x.get('title', '?')[:60]}")
    except Exception as e:
        print(f"Error: {e}")

def cmd_send_test(config):
    if not config.get("gmail", {}).get("email"):
        print("Gmail not configured")
        return
    print("Gmail configured. Test email would be sent.")

def cmd_trade_status(config):
    try:
        from trader import Trader
        p = Trader(config).get_portfolio()
        print("\nTrading Status")
        print(f"  Cash: ${p.get('cash', 0):.2f} "
              f"Equity: ${p.get('equity', 0):.2f}")
        for sym, pos in p.get("positions", {}).items():
            print(f"  {sym}: {pos.get('qty', 0)} "
                  f"@ ${pos.get('current_price', 0):.2f}")
    except Exception as e:
        print(f"Error: {e}")

def cmd_scan(config):
    try:
        from bounty_scanner import BountyScanner
        b = BountyScanner(config).scan_for_bounties()
        print(f"\nScan: found {len(b)} items")
        for x in b[-5:]:
            print(f"  [{x.get('difficulty', '?')}] "
                  f"{x.get('reward', 0)} "
                  f"{x.get('repo', '?')}:{x.get('path', '?')}")
    except Exception as e:
        print(f"Scan error: {e}")

def cmd_trade_scan(config):
    try:
        from trader import Trader
        from bounty_scanner import BountyScanner
        t = Trader(config)
        a = BountyScanner(config).get_alerts()
        if not a:
            print("No signals")
            return
        print(f"Trading: {len(a)} signals")
        for x in a:
            sig = {
                "repo": x.get("repo", ""),
                "bounty_amount": x.get("reward", 0),
                "difficulty": x.get("difficulty", "medium"),
                "trend": "up" if x.get("score", 0) >= 80 else "down",
            }
            r = t.execute_bounty_signal(sig)
            print(f"  {x.get('repo', '?')}: {r.get('status', '?')}")
    except Exception as e:
        print(f"Trade scan error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd_status({})
        sys.exit()
    cfg = load_config()
    cmds = {
        "status": cmd_status, "query": cmd_query,
        "send-test": cmd_send_test,
        "trade-status": cmd_trade_status,
        "scan": cmd_scan, "trade-scan": cmd_trade_scan,
    }
    cn = sys.argv[1].lower()
    if cn in cmds:
        cmds[cn](cfg)
    else:
        print(f"Unknown: {cn}")
