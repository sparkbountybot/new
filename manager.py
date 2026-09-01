"""
BountyBot Framework v2 — Automated Technical Trading & GitHub Bounty Hunting

Usage:
    python manager.py status            # Show system status
    python manager.py scan              # Scan GitHub bounties
    python manager.py trade-scan        # Execute trading signals
    python manager.py query             # View alerts/jobs
    python manager.py trade-status      # View trading positions
    python manager.py send-test         # Test email
    python manager.py run               # Full automated run
    python manager.py dashboard         # Show dashboard
    python manager.py schedule          # Start scheduler (background jobs)
    python manager.py monitor-status    # Live monitoring dashboard
    python manager.py monitor-history   # Scan history
"""
import sys, os, json, time, subprocess, platform
from datetime import datetime
from pathlib import Path

from config import load_config, load_state, save_state, get_state_dir
from bountybot.bounty_scanner import GitHubBountyHunter
from bountybot.trader import TechnicalTrader
from bountybot.gmail_monitor import GmailMonitor
from bountybot.mail_sender import EmailSender
from bountybot.scheduler import BountyScheduler
from bountybot.dashboard import simple_dashboard


def cmd_status(config):
    """Show system status."""
    print("\n" + "=" * 60)
    print("  BOUNTYBOT FRAMEWORK v2")
    print(f"  {datetime.utcnow().isoformat()} UTC")
    print("=" * 60)

    gh_token = config["github"].get("token", "")
    print(f"\n  [GITHUB]")
    print(f"    Status: {'Connected' if gh_token else 'No token'}")
    print(f"    Org: {config['github']['org']}")

    alpaca_key = config["trading"].get("alpaca_api_key", "")
    print(f"\n  [TRADING]")
    print(f"    Alpaca: {'Configured' if alpaca_key else 'Not configured'}")
    print(f"    Mode: {'Paper' if config['trading'].get('paper', True) else 'Live'}")

    gmail = config.get("gmail", {})
    print(f"\n  [GMAIL]")
    print(f"    Status: {'Configured' if gmail.get('email') and gmail.get('password') else 'Not configured'}")

    state_dir = get_state_dir()
    if state_dir.exists():
        files = list(state_dir.glob("*.json"))
        print(f"\n  [STATE] {len(files)} files")
        for f in sorted(files):
            size = f.stat().st_size
            print(f"    {f.name}: {size:,} bytes")

    print("\n" + "=" * 60)


def cmd_scan(config):
    """Scan GitHub for bounties."""
    hunter = GitHubBountyHunter(config)
    hunter.scan()


def cmd_trade_scan(config):
    """Execute trading signals."""
    trader = TechnicalTrader(config)
    result = trader.scan_and_trade()
    print(f"\n  Result: {json.dumps(result, indent=2, default=str)}")


def cmd_query(config):
    """View alerts and jobs."""
    hunter = GitHubBountyHunter(config)
    alerts = hunter.get_alerts()

    print(f"\n  === Active Alerts/Jobs ({len(alerts)}) ===")
    for i, a in enumerate(alerts, 1):
        print(f"\n  {i}. [{a['difficulty'].upper()}] ${a['reward']:>5} - {a['repo']}#{a['number']}")
        print(f"     {a['title'][:80]}")
        print(f"     Score: {a['score']} | {', '.join(a['reasons'][:3])}")
        print(f"     URL: {a['url']}")

    gm = GmailMonitor(config)
    if gm.connected:
        alerts_state = gm.get_alerts()
        if alerts_state:
            print(f"\n  === Gmail Alerts ({len(alerts_state)}) ===")
            for a in alerts_state[-5:]:
                print(f"    [{a['date'][:10]}] {a['subject']}")


def cmd_trade_status(config):
    """Show trading status."""
    trader = TechnicalTrader(config)
    portfolio = trader.get_portfolio()

    print(f"\n  === Trading Status ===")
    if "error" in portfolio:
        print(f"  {portfolio['error']}")
        return

    print(f"  Portfolio: ${portfolio.get('portfolio_value', 0):,.2f}")
    print(f"  Cash: ${portfolio.get('cash', 0):,.2f}")
    print(f"  Buying Power: ${portfolio.get('buying_power', 0):,.2f}")
    print(f"  Total P&L: ${portfolio.get('total_pnl', 0):,.2f}")
    print(f"  Positions: {portfolio.get('num_positions', 0)}")

    positions = [p for p in portfolio.get("positions", []) if "error" not in p]
    for p in positions:
        pnl = p.get("unrealized_pl", 0)
        print(f"    {p['symbol']}: {p['qty']} shares @ ${p['avg_entry_price']:.2f}")
        print(f"      Current: ${p['current_price']:.2f} | P&L: ${pnl:,.2f} ({p.get('unrealized_plpc', 0):+.1f}%)")


def cmd_send_test(config):
    """Test email sending."""
    sender = EmailSender(config)
    return sender.send_test()


from bountybot.dashboard import simple_dashboard


# === Monitoring ===

def _file_age_seconds(path):
    try:
        return time.time() - os.path.getmtime(path)
    except:
        return 99999


def cmd_monitor_status(config):
    """Live monitoring dashboard."""
    import platform
    from pathlib import Path as P
    now = datetime.utcnow()
    
    print("\n" + "=" * 72)
    print(f"  BOUNTYBOT LIVE STATUS  {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 72)
    
    hostname = platform.node()
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            gpu = result.stdout.strip().split(", ")
            print(f"\n  [SYSTEM] Host: {hostname}  GPU: {gpu[0]}  Util: {gpu[3]}%  Temp: {gpu[4]}°C")
    except:
        print(f"\n  [SYSTEM] Host: {hostname}")
    
    # Trading state
    try:
        from config import load_state
        trading = load_state("trading_session")
        if trading.get("signals"):
            signals = trading["signals"]
            buys = len([s for s in signals if s.get("action") in ("BUY", "WEAK_BUY")])
            sells = len([s for s in signals if s.get("action") in ("SELL", "WEAK_SELL")])
            timestamp = trading.get("timestamp", "unknown")
            print(f"\n  [TRADING] Last signal: {timestamp}")
            print(f"    Signals: BUY={buys} SELL={sells}  |  Total: {len(signals)}")
            strong = [s for s in signals if abs(s.get("net_score", 0)) >= 4]
            if strong:
                print(f"    Strong signals:")
                for s in strong:
                    print(f"      {s['symbol']}: {s['action']} (score: {s['net_score']:+d})")
        else:
            print(f"\n  [TRADING] No recent signals")
    except:
        print(f"\n  [TRADING] No state data")
    
    # Bounty state
    try:
        from config import load_state
        bounties = load_state("bounty_jobs")
        stats = bounties.get("stats", {})
        jobs = bounties.get("jobs", [])
        if jobs:
            total_reward = sum(j.get("reward", 0) for j in jobs)
            print(f"\n  [BOUNTIES] Jobs tracked: {len(jobs)}  Potential: ${total_reward:,}")
            print(f"    Scans: {stats.get('scans', 0)}  Last: {stats.get('last_scan', 'never')}")
        else:
            print(f"\n  [BOUNTIES] Scans: {stats.get('scans', 0)}  Jobs: 0  Last: {stats.get('last_scan', 'never')}")
    except:
        print(f"\n  [BOUNTIES] No state data")
    
    # State files
    try:
        from config import get_state_dir
        state_dir = get_state_dir()
        if state_dir.exists():
            files = list(state_dir.glob("*.json"))
            print(f"\n  [STATE FILES] {len(files)} files:")
            for f in sorted(files):
                age_min = _file_age_seconds(f) / 60
                age_str = f"{age_min:.0f}m ago" if age_min < 60 else f"{age_min/60:.1f}h ago"
                print(f"    {f.name:30s} {f.stat().st_size:>8,} bytes  ({age_str})")
    except:
        pass
    
    print("\n" + "=" * 72)


def cmd_monitor_history(config):
    """Show scan history."""
    from config import load_state
    print("\n" + "=" * 72)
    print("  BOUNTYBOT SCAN HISTORY")
    print("=" * 72)
    
    try:
        trading = load_state("trading_session")
        if trading.get("signals"):
            signals = trading["signals"]
            timestamp = trading.get("timestamp", "")
            buys = len([s for s in signals if s.get("action") in ("BUY", "WEAK_BUY")])
            sells = len([s for s in signals if s.get("action") in ("SELL", "WEAK_SELL")])
            print(f"\n  [{timestamp}]")
            print(f"    Signals: {len(signals)}  |  BUY: {buys}  SELL: {sells}")
            print()
            for s in signals:
                symbol = s["symbol"]
                action = s["action"]
                conf = s["confidence"]
                score = s["net_score"]
                rsi = s.get("indicators", {}).get("rsi_14", 0)
                macd = s.get("indicators", {}).get("macd", 0)
                bar = "█" * abs(score) if score > 0 else "░" * abs(score)
                bar = f"[{bar}]"
                print(f"    {symbol:8s} {action:12s} conf={conf:.2f}  RSI={rsi:5.1f}  MACD={macd:.3f}  {bar}")
        else:
            print("\n  No signals recorded yet.")
    except Exception as e:
        print(f"\n  Error reading state: {e}")
    
    print("\n" + "=" * 72)


def cmd_run(config):
    """Full automated run: scan bounties + trade + status."""
    print("\n" + "=" * 60)
    print("  BOUNTYBOT FULL RUN")
    print("=" * 60)

    hunter = GitHubBountyHunter(config)
    jobs = hunter.scan()

    trader = TechnicalTrader(config)
    if trader.is_connected:
        print("\n  Running trading engine...")
        trade_result = trader.scan_and_trade()
    else:
        print("\n  Skipping trading (Alpaca not configured or proxy block)")

    print(f"\n  === Run Complete ===")
    print(f"  Bounties scanned: {len(jobs)}")
    if trade_result and isinstance(trade_result, dict):
        print(f"  Trades executed: {trade_result.get('trades_executed', 0)}")


def cmd_dashboard(config):
    """Show dashboard."""
    hunter = GitHubBountyHunter(config)
    trader = TechnicalTrader(config)
    simple_dashboard(trader=trader, scanner=hunter, config=config)


def cmd_schedule(config):
    """Start scheduler for background jobs."""
    def main_run(mode="full"):
        if mode == "scan":
            cmd_scan(config)
        elif mode == "trade":
            cmd_trade_scan(config)
        elif mode == "status":
            cmd_status(config)
        else:
            cmd_run(config)

    sched = BountyScheduler(main_run, config)
    sched.setup()
    print("\nScheduler running. Press Ctrl+C to stop.")
    sched.start()


if __name__ == "__main__":
    config = load_config()
    cmds = {
        "status": cmd_status,
        "scan": cmd_scan,
        "trade-scan": cmd_trade_scan,
        "query": cmd_query,
        "trade-status": cmd_trade_status,
        "send-test": cmd_send_test,
        "run": cmd_run,
        "dashboard": cmd_dashboard,
        "schedule": cmd_schedule,
        "monitor-status": cmd_monitor_status,
        "monitor-history": cmd_monitor_history,
    }

    if len(sys.argv) < 2:
        cmd_status(config)
        print("\n  Commands: status, scan, trade-scan, query, trade-status, send-test, run, dashboard, schedule, monitor-status, monitor-history")
        sys.exit()

    cn = sys.argv[1].lower()
    if cn in cmds:
        cmds[cn](config)
    else:
        print(f"Unknown command: {cn}")
        print(f"Available: {', '.join(cmds.keys())}")
