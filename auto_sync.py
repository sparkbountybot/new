#!/usr/bin/env python3
"""
Auto-sync between sandboxes.
Pulls latest, checks for changes, updates notes.
Usage: python auto_sync.py [--push] [--evolve]
"""
import subprocess, json, os
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent

def run(cmd):
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE)
    return result.returncode == 0, result.stdout.strip() or result.stderr.strip()

def read_json(path, default=None):
    """Read JSON file."""
    p = Path(BASE) / path
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default if default is not None else []

def write_json(path, data):
    """Write JSON file."""
    with open(Path(BASE) / path, 'w') as f:
        json.dump(data, f, indent=2)

def add_to_notes(filepath, section, content):
    """Add content to a notes file under a section."""
    notes_path = Path(BASE) / filepath
    if notes_path.exists():
        with open(notes_path) as f:
            content_orig = f.read()
    else:
        content_orig = ""
    
    # Check if section exists
    if f"## {section}" in content_orig:
        # Insert before the section marker
        lines = content_orig.split('\n')
        new_lines = []
        inserted = False
        for line in lines:
            if line.strip() == f"## {section}" and not inserted:
                new_lines.append(content)
                new_lines.append(line)
                inserted = True
            else:
                new_lines.append(line)
        if not inserted:
            new_lines.append(f"\n## {section}")
            new_lines.append(content)
    else:
        new_lines = [content_orig, f"\n## {section}", content]
    
    with open(notes_path, 'w') as f:
        f.write('\n'.join(new_lines))

if __name__ == "__main__":
    import sys
    
    push = "--push" in sys.argv
    evolve = "--evolve" in sys.argv
    
    print(f"🔄 Auto-sync from {os.environ.get('NEMOCLAW_SANDBOX_NAME', 'unknown')}")
    print("=" * 60)
    
    # 1. Pull latest
    success, output = run("git pull origin main")
    if success:
        print(f"✅ Pulled: {output[:200]}")
    else:
        print(f"⚠️ Pull: {output[:200]}")
    
    # 2. Check spark2 notes
    spark2_notes = Path(BASE) / ".github/shared/spark2/notes.md"
    if spark2_notes.exists():
        with open(spark2_notes) as f:
            content = f.read()
        
        # Look for recent changes
        if "Recent discoveries by spark2" in content:
            print("\n📋 Spark2 notes loaded")
            # Extract the recent discoveries section
            start = content.find("## Recent discoveries by spark2")
            if start >= 0:
                end = content.find("---", start)
                if end < 0:
                    end = len(content)
                recent = content[start:end].strip()
                print(f"Recent spark2 work:\n{recent[:500]}")
    
    # 3. Check evolution status if --evolve flag
    if evolve:
        print("\n🧬 Running evolution cycle...")
        success, output = run(".venv/bin/python3 evolution_engine.py --run")
        if success:
            print(f"✅ Evolution: {output[:300]}")
        else:
            print(f"⚠️ Evolution failed: {output[:300]}")
        
        # Read updated knowledge base
        kb_path = Path(BASE) / "knowledge_base.md"
        if kb_path.exists():
            with open(kb_path) as f:
                kb = f.read()
            if kb and kb.strip():
                add_to_notes(".github/shared/spark3/notes.md", "Self-Improvement Insights", f"Knowledge base updated:\n{kb[:500]}")
    
    # 4. Log evolution if we have experience data
    exp_log = Path(BASE) / "experience_log.json"
    if exp_log.exists():
        try:
            exp_data = json.load(open(exp_log))
            if isinstance(exp_data, list):
                total = len(exp_data)
                completed = sum(1 for e in exp_data if isinstance(e, dict) and e.get("outcome") != "pending")
                pending = total - completed
                
                add_to_notes(".github/shared/spark3/notes.md", "Experience Progress", 
                    f"Experience log: {total} total, {completed} completed, {pending} pending")
        except:
            pass
    
    # 5. Push if requested
    if push:
        print("\n📤 Pushing changes...")
        run("git add -A")
        run(f'git commit -m "Auto-sync {datetime.now().strftime("%Y-%m-%d %H:%M")}"')
        success, output = run("git push origin main")
        if success:
            print(f"✅ Pushed: {output[:200]}")
        else:
            print(f"⚠️ Push: {output[:200]}")
    
    print("\n✅ Sync complete")
