"""Sync script — pull, log changes, push. Both sandboxes use this."""
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent

def log_change(action, details):
    """Log a sync event."""
    log_path = BASE_DIR / "sync_log.json"
    import json
    log = []
    if log_path.exists():
        with open(log_path) as f:
            try:
                log = json.load(f)
            except:
                log = []
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
    }
    log.append(entry)
    
    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

def git_pull():
    """Pull latest from remote."""
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        return result.returncode == 0, result.stdout
    except Exception as e:
        return False, str(e)

def git_push():
    """Push to remote."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        subprocess.run(
            ["git", "commit", "-m", f"Sync from {__import__('socket').gethostname()} at {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        return result.returncode == 0, result.stdout
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print(f"Syncing from {__import__('socket').gethostname()}...")
    
    # Pull first
    success, output = git_pull()
    if success:
        print("✅ Pulled latest")
        log_change("pull", output.strip() if output else "no changes")
    else:
        print(f"⚠️  Pull failed: {output}")
        log_change("pull_failed", output.strip() if output else "error")
    
    # Check evolution status
    try:
        import subprocess
        result = subprocess.run(
            ["python3", str(BASE_DIR / "evolution_engine.py"), "--status"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        print(result.stdout)
    except Exception as e:
        print(f"⚠️  Could not check evolution status: {e}")
    
    # Push
    success, output = git_push()
    if success:
        print("✅ Pushed changes")
        log_change("push", output.strip() if output else "no changes to push")
    else:
        print(f"⚠️  Push failed: {output}")
        log_change("push_failed", output.strip() if output else "error")
