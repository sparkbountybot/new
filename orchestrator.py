#!/usr/bin/env python3
"""
Orchestrator — coordinates work between spark2 and spark3

Run from host terminal:
  python3 orchestrator.py
"""
import subprocess
import json
import os
from datetime import datetime, timezone

HOST_HOME = os.environ.get("HOME", "/home/machine_learning")
SPARK2_DIR = os.path.join(HOST_HOME, ".docker", "volumes", "spark2", "_data")
SPARK3_DIR = os.path.join(HOST_HOME, ".docker", "volumes", "spark3", "_data")

# More reliable: check sandbox env
SPARK2_ID = os.environ.get("SPARK2_ID", "openshell-default--spark2-0d9a3473-33c1-4700-a0cb-4bec6183a08d")
SPARK3_ID = os.environ.get("SPARK3_ID", "openshell-default--spark3-b8669437-96ff-4e1a-aa90-21c50772f075")


def run_in_sandbox(sandbox_id, command, timeout=60):
    """Run command in a specific sandbox"""
    try:
        result = subprocess.run(
            ["openshell", "exec", sandbox_id, "--", "python3", "-c", command],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout + result.stderr, result.returncode
    except Exception as e:
        return str(e), 1


def check_sandbox_status():
    """Check if both sandboxes are running"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", '{{.Names}}'],
            capture_output=True, text=True, timeout=10
        )
        containers = result.stdout.strip().split('\n')
        status = {}
        for c in containers:
            if 'spark2' in c:
                status['spark2'] = 'running'
            elif 'spark3' in c:
                status['spark3'] = 'running'
        return status
    except:
        return {'spark2': 'unknown', 'spark3': 'unknown'}


def main():
    print("=" * 60)
    print("  ORCHESTRATOR — Spark2 ↔ Spark3 Coordination")
    print("=" * 60)
    
    print(f"\n[1/4] Checking sandbox status...")
    status = check_sandbox_status()
    for box, s in status.items():
        icon = "✓" if s == "running" else "✗"
        print(f"  {icon} {box}: {s}")
    
    print("\n[2/4] Syncing shared agenda...")
    # Pull latest from GitHub
    subprocess.run(["git", "-C", os.path.join(HOST_HOME, "new"), "pull", "origin", "main"], 
                  capture_output=True, timeout=30)
    print("  Agenda pulled from GitHub")
    
    print("\n[3/4] Coordinating actions...")
    
    # Read shared state
    state_file = os.path.join(HOST_HOME, "new", ".github", "shared", "sync_state.json")
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
        
        print(f"  Last sync: {state.get('last_sync', 'never')}")
        print(f"  Actions: {len(state.get('actions', []))}")
        
        # Show pending/active actions
        for a in state.get("actions", []):
            if a["status"] in ["pending", "active"]:
                print(f"    {a['id']}: {a['description']} [{a['assigned_to']}]")
    else:
        print("  No shared state yet (first sync)")
        state = {"actions": [], "last_sync": None}
    
    print("\n[4/4] Running sync protocol...")
    # Run sync check-in in spark2
    cmd2 = "from sync_protocol import SyncProtocol; s = SyncProtocol('spark2'); s.sync()"
    out2, rc2 = run_in_sandbox(SPARK2_ID, cmd2)
    if rc2 == 0:
        print("  Spark2: sync OK")
    else:
        print(f"  Spark2: {out2[:100]}")
    
    # Run sync check-in in spark3
    cmd3 = "from sync_protocol import SyncProtocol; s = SyncProtocol('spark3'); s.sync()"
    out3, rc3 = run_in_sandbox(SPARK3_ID, cmd3)
    if rc3 == 0:
        print("  Spark3: sync OK")
    else:
        print(f"  Spark3: {out3[:100]}")
    
    # Push merged state back to GitHub
    subprocess.run(["git", "-C", os.path.join(HOST_HOME, "new"), "add", "."], 
                  capture_output=True, timeout=10)
    subprocess.run(["git", "-C", os.path.join(HOST_HOME, "new"), "commit", 
                   "-m", f"sync: orchestrator coordination {datetime.now(timezone.utc).strftime('%H:%M')}"], 
                  capture_output=True, timeout=10)
    subprocess.run(["git", "-C", os.path.join(HOST_HOME, "new"), "push", "origin", "main"], 
                  capture_output=True, timeout=30)
    
    print(f"\n=== ORCHESTRATOR COMPLETE ===\n")


if __name__ == "__main__":
    main()
