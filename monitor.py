"""
BountyBot Monitor — Live status and history tracking.
Run: python monitor.py status    # Current state
     python monitor.py history   # Historical scans
     python monitor.py watch     # Continuous live monitoring
     python monitor.py check     # Health check (for cron/alerting)
"""
import sys, os, json, time, subprocess, platform
from datetime import datetime, timedelta
from pathlib import Path

try:
    from config import load_config, get_state_dir, load_state
except:
    pass

def _count_lines_file(path):
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except:
        return 0

def _file_age_seconds(path):
    try:
        return time.time() - os.path.getmtime(path)
    except:
        return 99999

def cmd_status():
    """Print live status dashboard."""
    now = datetime.utcnow()
    
    print("\n" + "=" * 72)
    print(f"  BOUNTYBOT LIVE STATUS  {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 72)

    # System info
    hostname = platform.node()
    try:
        gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                                    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if gpu_info.returncode == 0:
            gpu = gpu_info.stdout.strip().split(", ")
            print(f"\n  [SYSTEM] Host: {hostname}  GPU: {gpu[0]}  RAM: {gpu[1]}/{gpu[2]}GB  "
                  f"Util: {gpu[3]}%  Temp: {gpu[4]}°C")
    except:
        print(f"\n  [SYSTEM] Host: {hostname}  (GPU info unavailable)")

    # Python process info
    try:
        result = subprocess.run(["ps", "aux", "|", "grep", "manager.py", "|", "grep", "-v", "grep"], 
                               shell=True, capture_output=True, text=True, timeout=5)
        processes = result.stdout.strip().split("\n")
        active_processes = [p for p in processes if p and "grep" not in p]
        print(f"  [PROCESSES] Active: {len(active_processes)}")
        for p in active_processes[:3]:
            parts = p.split()
            if len(parts) >= 10:
                print(f"    PID: {parts[1]}  USER: {parts[0]}  CPU: {parts[2]}%  MEM: {parts[3]}%  CMD: {' '.join(parts[10:])}")
    except:
        pass

    # Trading state
    try:
        trading = load_state("trading_session")
        if trading.get("signals"):
            signals = trading["signals"]
            buys = len([s for s in signals if s.get("action") in ("BUY", "WEAK_BUY")])
            sells = len([s for s in signals if s.get("action") in ("SELL", "WEAK_SELL")])
            holds = len(signals) - buys - sells
            timestamp = trading.get("timestamp", "unknown")
            print(f"\n  [TRADING] Last signal: {timestamp}")
            print(f"    Signals: {len(signals)} total  |  BUY: {buys}  SELL: {sells}  HOLD: {holds}")
            
            # Show top signals
            strong = [s for s in signals if abs(s.get("net_score", 0)) >= 4]
            if strong:
                print(f"    Strong signals:")
                for s in strong:
                    print(f"      {s['symbol']}: {s['action']} (score: {s['net_score']:+d}, conf: {s['confidence']:.2f})")
        else:
            print(f"\n  [TRADING] No recent signals")
    except Exception as e:
        print(f"\n  [TRADING] Error reading state: {e}")

    # Bounty state
    try:
        bounties = load_state("bounty_jobs")
        stats = bounties.get("stats", {})
        jobs = bounties.get("jobs", [])
        if jobs:
            top_job = jobs[0] if jobs else {}
            total_reward = sum(j.get("reward", 0) for j in jobs)
            print(f"\n  [BOUNTIES] Jobs tracked: {len(jobs)}  Total potential: ${total_reward:,}")
            print(f"    Scans: {stats.get('scans', 0)}  Last: {stats.get('last_scan', 'never')}")
            if top_job:
                print(f"    Top: {top_job['title'][:60]}... (${top_job.get('reward', 0)} score: {top_job.get('score', 0)})")
        else:
            print(f"\n  [BOUNTIES] Scans: {stats.get('scans', 0)}  Jobs: 0  Last: {stats.get('last_scan', 'never')}")
    except:
        print(f"\n  [BOUNTIES] No state data")

    # State files
    try:
        state_dir = get_state_dir()
        if state_dir.exists():
            files = list(state_dir.glob("*.json"))
            print(f"\n  [STATE FILES] {len(files)} files in state/")
            for f in sorted(files):
                age_min = _file_age_seconds(f) / 60
                size = f.stat().st_size
                age_str = f"{age_min:.0f}m ago" if age_min < 60 else f"{age_min/60:.1f}h ago"
                print(f"    {f.name:30s} {size:>8,} bytes  ({age_str})")
    except:
        print(f"\n  [STATE FILES] Error reading state directory")

    # GitHub Actions status
    try:
        result = subprocess.run(["gh", "api", "repos/sparkbountybot/new/actions/runs", 
                                "-q", ".[:5].id, .[:5].status, .[:5].conclusion, .[:5].created_at"],
                               capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            runs = result.stdout.strip().split("\n")[:5]
            print(f"\n  [GITHUB ACTIONS] Recent runs:")
            for run in runs:
                if run:
                    parts = run.split(",")
                    if len(parts) >= 4:
                        status = parts[1] if len(parts) > 1 else "unknown"
                        conclusion = parts[2] if len(parts) > 2 else "unknown"
                        created = parts[3][:16] if len(parts) > 3 else "unknown"
                        icon = {"success": "✓", "failure": "✗", "in_progress": "⟳", "queued": "◌"}
                        icon_char = icon.get(conclusion, "?")
                        print(f"    Run #{parts[0]}  {icon_char}{conclusion:15s}  {created}  (id: {parts[0]})")
    except:
        print(f"\n  [GITHUB ACTIONS] Cannot check (gh CLI or network)")

    print("\n" + "=" * 72)

def cmd_history():
    """Show scan history from state files."""
    print("\n" + "=" * 72)
    print("  BOUNTYBOT SCAN HISTORY")
    print("=" * 72)

    state_dir = get_state_dir()
    if not state_dir.exists():
        print("  No state directory found.")
        return

    print("\n  Trading Sessions:")
    print("  " + "-" * 68)
    
    try:
        trading = load_state("trading_session")
        if trading.get("signals"):
            signals = trading["signals"]
            timestamp = trading.get("timestamp", "")
            trades_count = len(trading.get("trades", []))
            
            buys = len([s for s in signals if s.get("action") in ("BUY", "WEAK_BUY")])
            sells = len([s for s in signals if s.get("action") in ("SELL", "WEAK_SELL")])
            
            print(f"  [{timestamp}]")
            print(f"    Total signals: {len(signals)}  |  BUY: {buys}  SELL: {sells}  EXECUTED: {trades_count}")
            print()
            
            for s in signals:
                symbol = s["symbol"]
                action = s["action"]
                conf = s["confidence"]
                score = s["net_score"]
                rsi = s.get("indicators", {}).get("rsi_14", 0)
                macd = s.get("indicators", {}).get("macd", 0)
                
                bar_length = int(abs(score) * 3)
                bar = "█" * bar_length if score > 0 else "░" * bar_length
                bar = f"[{bar}]" if bar else "[]"
                
                print(f"    {symbol:8s} {action:12s} conf={conf:.2f}  RSI={rsi:5.1f}  MACD={macd:.3f}  {bar}")
        else:
            print("  No signals recorded yet.")
    except Exception as e:
        print(f"  Error reading trading state: {e}")

    print("\n  Bounty Scans:")
    print("  " + "-" * 68)
    try:
        bounties = load_state("bounty_jobs")
        stats = bounties.get("stats", {})
        jobs = bounties.get("jobs", [])
        print(f"  Total scans: {stats.get('scans', 0)}")
        print(f"  Total jobs tracked: {stats.get('total_jobs', 0)}")
        print(f"  Last scan: {stats.get('last_scan', 'never')}")
        
        if jobs:
            print(f"\n  Top jobs by score:")
            for i, job in enumerate(jobs[:5], 1):
                print(f"    {i}. [{job.get('difficulty', 'unknown'):6s}] ${job.get('reward', 0):>5}  {job['repo']}#{job['number']}")
                print(f"       {job['title'][:70]}")
                print(f"       Score: {job.get('score', 0)}  |  {', '.join(job.get('reasons', [])[:2])}")
    except Exception as e:
        print(f"  Error reading bounty state: {e}")

    print("\n" + "=" * 72)

def cmd_watch():
    """Continuous monitoring loop."""
    print("\n  BOUNTYBOT LIVE WATCH  (Press Ctrl+C to stop)")
    print("  " + "=" * 60)
    
    last_trading_time = None
    last_bounty_time = None
    trades_seen = set()
    
    try:
        while True:
            now = datetime.utcnow()
            
            # Get current trading state
            try:
                trading = load_state("trading_session")
                if trading.get("timestamp"):
                    ts = trading["timestamp"]
                    if ts != last_trading_time:
                        last_trading_time = ts
                        signals = trading["signals"]
                        buys = len([s for s in signals if s.get("action") in ("BUY", "WEAK_BUY")])
                        sells = len([s for s in signals if s.get("action") in ("SELL", "WEAK_SELL")])
                        holds = len(signals) - buys - sells
                        
                        print(f"\n  [{now.strftime('%H:%M:%S')}] Trading update:")
                        print(f"    Timestamp: {ts}")
                        print(f"    Signals: BUY={buys} SELL={sells} HOLD={holds}  |  Total: {len(signals)}")
                        
                        for s in signals[:3]:
                            print(f"      {s['symbol']}: {s['action']} (score: {s['net_score']:+d})")
            except:
                pass
            
            # Check for new trades (new order IDs)
            try:
                trading = load_state("trading_session")
                for t in trading.get("trades", []):
                    order_id = t.get("order_id", "")
                    if order_id and order_id not in trades_seen:
                        trades_seen.add(order_id)
                        print(f"\n  *** NEW TRADE: {t.get('symbol', '?')} {t.get('action', '?')} {t.get('qty', '?')}")
            except:
                pass
            
            # Check bounty scans
            try:
                bounties = load_state("bounty_jobs")
                stats = bounties.get("stats", {})
                jobs = bounties.get("jobs", [])
                last_scan = stats.get("last_scan", "")
                
                if last_scan != last_bounty_time and last_scan:
                    last_bounty_time = last_scan
                    print(f"\n  [{now.strftime('%H:%M:%S')}] Bounty scan:")
                    print(f"    Scans: {stats.get('scans', 0)}  Jobs: {len(jobs)}  Last: {last_scan[:19]}")
            except:
                pass
            
            time.sleep(15)
            
    except KeyboardInterrupt:
        print(f"\n  Stopped watching.")

def cmd_check():
    """Health check — suitable for cron/alerting."""
    try:
        trading = load_state("trading_session")
        bounties = load_state("bounty_jobs")
        state_dir = get_state_dir()
        state_files = list(state_dir.glob("*.json")) if state_dir.exists() else []
        
        print(json.dumps({
            "status": "ok",
            "last_trading": trading.get("timestamp"),
            "trading_signals": len(trading.get("signals", [])),
            "last_bounty_scan": bounties.get("stats", {}).get("last_scan"),
            "bounty_jobs": len(bounties.get("jobs", [])),
            "total_bounty_scans": bounties.get("stats", {}).get("scans", 0),
            "state_files": len(state_files),
            "timestamp": datetime.utcnow().isoformat()
        }))
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}))
        return 1

if __name__ == "__main__":
    commands = {
        "status": cmd_status,
        "history": cmd_history,
        "watch": cmd_watch,
        "check": cmd_check,
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("BountyBot Monitor")
        print("Usage: python monitor.py [status|history|watch|check]")
        print("  status  - Live dashboard with current state")
        print("  history - Historical scan data")
        print("  watch   - Continuous live monitoring")
        print("  check   - Health check output (for cron/alerting)")
        sys.exit(1)
    
    commands[sys.argv[1]]()
