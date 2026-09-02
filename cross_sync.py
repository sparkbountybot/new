#!/usr/bin/env python3
"""
Cross-sandbox sync — discover changes, communicate with other sandbox.
Both sandboxes run this to stay in sync.

Usage: python cross_sync.py [--push]
"""
import subprocess, json, os
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
SPARK2_NOTES = BASE / ".github/shared/spark2/notes.md"
SPARK3_NOTES = BASE / ".github/shared/spark3/notes.md"
ACTIVE_MD = BASE / ".github/shared/active.md"
DECISIONS_MD = BASE / ".github/shared/decisions.md"


def run(cmd):
    """Run shell command, return (success, output)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE)
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())


def read_file(path):
    """Read file content."""
    if path.exists():
        return path.read_text()
    return ""


def append_to_file(path, content):
    """Append content to a file (create if missing)."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    
    with open(path, 'a') as f:
        f.write("\n" + content + "\n")


def update_active_md(sandbox_name):
    """Update who's active/working."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        "# Who's working on what (active.md)",
        "",
        f"**Last updated:** {sandbox_name} | {now}",
        "",
        "## Active Sessions",
        "",
    ]
    
    for sname in ["spark2", "spark3"]:
        notes_path = BASE / f".github/shared/{sname}/notes.md"
        if notes_path.exists():
            with open(notes_path) as f:
                content = f.read()
            
            # Find "What I'm working on" section
            in_work = False
            work_items = []
            for line in content.split('\n'):
                if "What I'm working on" in line:
                    in_work = True
                    continue
                if in_work:
                    if line.strip().startswith('- '):
                        work_items.append(line.strip())
                    elif line.strip() and not line.startswith('##'):
                        break
            
            lines.append(f"### {sname}")
            if work_items:
                lines.extend(work_items[:5])  # Top 5 items
            else:
                lines.append("  - No active items")
            lines.append("")
    
    with open(ACTIVE_MD, 'w') as f:
        f.write('\n'.join(lines))


def discover_changes():
    """Discover what the other sandbox has changed."""
    changes = []
    
    # Read the other sandbox's notes
    me = os.environ.get('NEMOCLAW_SANDBOX_NAME', 'spark3')
    them = 'spark2' if me == 'spark3' else 'spark3'
    
    notes_path = BASE / f".github/shared/{them}/notes.md"
    if notes_path.exists():
        content = notes_path.read_text()
        changes.append(f"## {them} Notes\n")
        
        # Extract key sections
        for section in ["Key files", "What I'm working on", "Recent discoveries", "Network status", "Immediate priorities"]:
            in_section = False
            items = []
            for line in content.split('\n'):
                if section in line:
                    in_section = True
                    continue
                if in_section:
                    if line.strip().startswith('- '):
                        items.append(line.strip())
                    elif line.strip().startswith('##') and line != section:
                        break
                    elif line.strip():
                        items.append(line.strip())
            
            if items:
                changes.append(f"\n### {section.replace(' ', '_').lower()}\n")
                changes.extend(items[:10])
    
    # Read evolution status
    exp_log = BASE / "experience_log.json"
    if exp_log.exists():
        try:
            data = json.loads(exp_log.read_text())
            if isinstance(data, list):
                total = len(data)
                completed = sum(1 for e in data if isinstance(e, dict) and e.get("outcome") != "pending")
                changes.append(f"\n## Experience Log\n- Total: {total} experiences\n- Completed: {completed}\n- Pending: {total - completed}")
        except:
            pass
    
    return '\n'.join(changes)


if __name__ == "__main__":
    import sys
    
    push = "--push" in sys.argv
    
    me = os.environ.get('NEMOCLAW_SANDBOX_NAME', 'unknown')
    print(f"🔄 Cross-sandbox sync from {me}")
    print("=" * 60)
    
    # 1. Pull latest
    success, output = run("git pull origin main")
    if success:
        if output and "Already up to date" not in output:
            print(f"✅ Pulled changes")
        else:
            print("✅ Up to date")
    else:
        print(f"⚠️ Pull: {output[:200]}")
    
    # 2. Discover changes from other sandbox
    print("\n📋 Discovering changes...")
    changes = discover_changes()
    if changes.strip():
        print(changes[:500])
        
        # Write to local notes
        my_notes = BASE / f".github/shared/{me}/notes.md"
        if my_notes.exists():
            with open(my_notes) as f:
                content = f.read()
            
            if "Discoveries from cross-sandbox sync" not in content:
                my_notes.write_text(content + f"\n\n## Discoveries from cross-sandbox sync\n{changes}\n")
            else:
                # Replace section if it exists
                lines = content.split('\n')
                new_lines = []
                skip = False
                for line in lines:
                    if "Discoveries from cross-sandbox sync" in line:
                        skip = True
                        new_lines.append(f"## Discoveries from cross-sandbox sync (updated {datetime.now().strftime('%Y-%m-%d %H:%M')})")
                        new_lines.append(changes)
                    elif skip:
                        if line.startswith('## '):
                            skip = False
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                my_notes.write_text('\n'.join(new_lines))
    else:
        print("  No new changes detected")
    
    # 3. Run evolution if available
    evolve_script = BASE / "evolution_engine.py"
    if evolve_script.exists():
        try:
            success, output = run(".venv/bin/python3 evolution_engine.py --status")
            if success and output:
                print(f"\n🧬 Evolution status:\n{output[:300]}")
        except:
            pass
    
    # 4. Update active.md
    update_active_md(me)
    print(f"\n✅ Updated active.md for {me}")
    
    # 5. Push if requested
    if push:
        print("\n📤 Pushing changes...")
        run("git add -A")
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        commit_msg = f'Cross-sync {me} at {ts}'
        run(f'git commit -m "{commit_msg}"')
        success, output = run("git push origin main")
        if success:
            print(f"✅ Pushed")
        else:
            print(f"⚠️ Push: {output[:200]}")
    
    print("\n✅ Sync complete")
