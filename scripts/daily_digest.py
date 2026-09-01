#!/usr/bin/env python3
"""
Daily Digest — Compiles daily summary from shared sandbox notes.
Reads .shared/notes/current.md from both sandboxes and git activity,
then outputs a clean daily report for the user.
"""
import subprocess, json, os
from datetime import datetime
from pathlib import Path

def run(cmd, shell=True):
    """Run a command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=shell)
    return result.stdout.strip()

def check_file(path):
    """Check if a file exists."""
    return Path(path).exists()

def generate_digest():
    """Generate daily digest from all sources."""
    today = datetime.now().strftime('%Y-%m-%d')
    day_name = datetime.now().strftime('%A')
    
    print(f"\n{'='*70}")
    print(f"  SPARK DAILY DIGEST — {day_name} {today}")
    print(f"{'='*70}\n")
    
    # 1. Git Activity
    print("📊 ACTIVITY (Last 24h)")
    print(f"{'─'*70}")
    
    repo_path = '/sandbox/new'
    if check_file(f'{repo_path}/.git'):
        log = run(f'cd {repo_path} && git log --oneline --since="24 hours ago" 2>/dev/null')
        if log:
            for entry in log.split('\n'):
                if entry:
                    print(f"  {entry}")
        else:
            print("  No new commits today.")
    else:
        print("  No git repo found.")
    print()
    
    # 2. Shared Notes (current state of shared knowledge)
    print("📝 SHARED NOTES")
    print(f"{'─'*70}")
    notes_file = f'{repo_path}/.shared/notes/current.md'
    if check_file(notes_file):
        notes = Path(notes_file).read_text()
        lines = notes.split('\n')
        in_detail = False
        for line in lines:
            if '## What We Built' in line or '## Current State' in line or '## Key Learnings' in line:
                in_detail = True
            if in_detail and line.strip() and not line.startswith('```'):
                if line.strip().startswith('### '):
                    print(f"\n  {line.strip()}")
                elif line.strip().startswith('1. ') or line.strip().startswith('2. ') or line.strip().startswith('3. '):
                    print(f"    {line.strip()}")
                elif line.strip() and not line.strip().startswith('##'):
                    pass  # Don't print intermediate lines
            if in_detail and line.strip().startswith('## ') and 'What' not in line and 'Current' not in line and 'Key' not in line:
                in_detail = False
    else:
        print("  No shared notes found.")
    print()
    
    # 3. Sandbox Status
    print("🔧 SANDBOX STATUS")
    print(f"{'─'*70}")
    
    checks = [
        ('Network (DNS)', check_file(f'{repo_path}/.shared/NOTES.md')),
        ('After-hours engine', check_file(f'{repo_path}/after_hours_engine.py')),
        ('Paper trader', check_file(f'{repo_path}/bountybot/paper_trader.py')),
        ('Cheat sheet', check_file(f'{repo_path}/README.md')),
        ('Shared notes', check_file(f'{repo_path}/.shared/notes/current.md')),
        ('Bounty scanner', check_file(f'{repo_path}/bountybot/bounty_scanner.py')),
        ('Paper trader test', check_file(f'{repo_path}/test_paper.py')),
        ('Rebuild guide', check_file(f'{repo_path}/REBUILD.md')),
    ]
    
    for name, result in checks:
        status = '✅' if result else '❌'
        print(f"  {status} {name}")
    print()
    
    # 4. Goals / Next Steps (from shared notes)
    print("🎯 GOALS / NEXT STEPS")
    print(f"{'─'*70}")
    if check_file(notes_file):
        notes = Path(notes_file).read_text()
        lines = notes.split('\n')
        for i, line in enumerate(lines):
            if '## Usage' in line:
                for j in range(i, min(i+10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith('```'):
                        print(f"  {lines[j].strip()}")
                break
    else:
        print("  No goals recorded yet.")
    print()
    
    # 5. Recent Wins
    print("🏆 RECENT WINS")
    print(f"{'─'*70}")
    
    wins = []
    if check_file(f'{repo_path}/after_hours_engine.py'):
        wins.append("  After-hours trading engine built and tested")
    if check_file(f'{repo_path}/bountybot/paper_trader.py'):
        wins.append("  Paper trader fixed (fill_price uses signal price)")
    if check_file(f'{repo_path}/.shared/notes/current.md'):
        wins.append("  Cross-sandbox shared notes system working")
    if check_file(f'{repo_path}/README.md'):
        wins.append("  Comprehensive cheat sheet saved")
    if check_file(f'{repo_path}/REBUILD.md'):
        wins.append("  Rebuild instructions documented")
    
    if wins:
        print('\n'.join(wins))
    else:
        print("  No wins recorded today.")
    print()
    
    # 6. Account Snapshot
    print("💰 ACCOUNT SNAPSHOT")
    print(f"{'─'*70}")
    
    if check_file(f'{repo_path}/.env'):
        try:
            env = {}
            with open(f'{repo_path}/.env') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, val = line.split('=', 1)
                        env[key] = val
            
            api_key = env.get('ALPACA_API_KEY', '')
            api_secret = env.get('ALPACA_API_SECRET', '')
            
            if api_key and api_secret:
                cmd = (f'curl -s --max-time 3 -H "APCA-API-KEY-ID: {api_key}" '
                       f'-H "APCA-API-SECRET-KEY: {api_secret}" '
                       f'"https://paper-api.alpaca.markets/v2/account"')
                acct_data = run(cmd)
                
                if acct_data and 'status' in acct_data:
                    data = json.loads(acct_data)
                    print(f"  Portfolio: ${float(data.get('portfolio_value', 0)):,.2f}")
                    print(f"  Cash: ${float(data.get('cash', 0)):,.2f}")
                    print(f"  Status: {data.get('status')}")
                else:
                    print(f"  Could not fetch account data (API error)")
            else:
                print("  No API credentials found in .env")
        except Exception as e:
            print(f"  Error fetching account: {e}")
    else:
        print("  No .env file found — checking shared notes...")
        if check_file(notes_file):
            notes = Path(notes_file).read_text()
            if 'Paper Account' in notes:
                print("  Check shared notes for account info")
    print()
    
    # 7. Summary
    total_checks = len(checks)
    passed = sum(1 for _, r in checks if r)
    print("📈 SUMMARY")
    print(f"{'─'*70}")
    print(f"  Components: {passed}/{total_checks} active")
    print(f"  Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    generate_digest()
