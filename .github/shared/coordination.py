#!/usr/bin/env python3
"""
Cross-sandbox coordination protocol
Prevents duplicate work, enables sharing, regular check-ins.
Both sandboxes run this independently — each claims what it does, sees what the other did.
"""
import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

SHARED = Path(__file__).parent / ".github" / "shared"
TASKS_FILE = SHARED / "work_items.json"

class Coordination:
    """Coordinates work between spark2 and spark3"""
    
    def __init__(self, my_id):
        self.my_id = my_id  # "spark2" or "spark3"
        self.SHARED = SHARED
        self.SHARED.mkdir(parents=True, exist_ok=True)
    
    def get_tasks(self):
        """Read current tasks from shared file"""
        if TASKS_FILE.exists():
            with open(TASKS_FILE) as f:
                return json.load(f)
        return {"tasks": [], "last_sync": None}
    
    def save_tasks(self, data):
        """Write tasks to shared file"""
        data["last_sync"] = datetime.now(timezone.utc).isoformat()
        with open(TASKS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def claim_task(self, task_id, description, category=None):
        """Claim a task — if other sandbox has it, skip. If done, skip."""
        data = self.get_tasks()
        
        for t in data["tasks"]:
            if t["task_id"] == task_id:
                if t["status"] == "done":
                    return {"action": "skip", "reason": "already done"}
                if t["status"] == "running" and t["claimed_by"] != self.my_id:
                    return {"action": "skip", "reason": f"running in {t['claimed_by']}"}
                if t["status"] == "running" and t["claimed_by"] == self.my_id:
                    return {"action": "continue", "reason": "already claimed by me"}
        
        task = {
            "task_id": task_id,
            "description": description,
            "category": category or "general",
            "status": "running",
            "claimed_by": self.my_id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "result": None
        }
        data["tasks"].append(task)
        self.save_tasks(data)
        return {"action": "claimed", "task_id": task_id}
    
    def complete_task(self, task_id, result_summary):
        """Mark a task as done"""
        data = self.get_tasks()
        for t in data["tasks"]:
            if t["task_id"] == task_id and t["claimed_by"] == self.my_id:
                t["status"] = "done"
                t["completed_at"] = datetime.now(timezone.utc).isoformat()
                t["result"] = result_summary
                self.save_tasks(data)
                return {"action": "done", "task_id": task_id}
        return {"action": "not_found", "reason": f"task {task_id} not claimed by {self.my_id}"}
    
    def list_tasks(self, show_all=False):
        """List tasks — running (mine), running (theirs), done"""
        data = self.get_tasks()
        tasks = data.get("tasks", [])
        
        my_running = [t for t in tasks if t["status"] == "running" and t["claimed_by"] == self.my_id]
        their_running = [t for t in tasks if t["status"] == "running" and t["claimed_by"] != self.my_id]
        done = [t for t in tasks if t["status"] == "done"]
        
        return {
            "my_running": my_running,
            "their_running": their_running,
            "done": done,
            "total": len(tasks)
        }
    
    def check_in(self):
        """Full check-in: show status, claim if needed, report"""
        result = self.list_tasks()
        
        print(f"\n{'='*60}")
        print(f"  CHECK-IN: {self.my_id}")
        print(f"  Last sync: {self.get_tasks().get('last_sync', 'never')}")
        print(f"{'='*60}")
        
        if result["my_running"]:
            print(f"\n📋 MY TASKS ({len(result['my_running'])} running):")
            for t in result["my_running"]:
                print(f"  ● {t['task_id']}: {t['description']}")
        
        if result["their_running"]:
            print(f"\n👤 THEIR TASKS ({len(result['their_running'])} running):")
            for t in result["their_running"]:
                print(f"  ○ {t['task_id']}: {t['description']} (by {t['claimed_by']})")
        
        if result["done"]:
            print(f"\n✅ DONE ({len(result['done'])}):")
            for t in result["done"][-5:]:  # Last 5
                print(f"  ✓ {t['task_id']}: {t['description'][:60]}")
        
        print(f"\n{'='*60}\n")
        
        return result
    
    def should_take_task(self, task_id, description):
        """Check if I should do a task or the other sandbox already has it"""
        result = self.should_take_task.__wrapped__(task_id, description) if hasattr(self.should_take_task, '__wrapped__') else None
        check = self.claim_task(task_id, description)
        if check["action"] == "skip":
            print(f"  SKIP: {check['reason']}")
            return False
        print(f"  TAKE: {task_id} — {description}")
        return True


if __name__ == "__main__":
    import sys
    
    # Auto-detect from command line first, then path
    my_id = sys.argv[1] if len(sys.argv) > 1 else "spark3"
    
    coord = Coordination(my_id)
    
    if len(sys.argv) > 2 and sys.argv[1] == "checkin":
        coord.check_in()
    elif len(sys.argv) > 3 and sys.argv[1] == "claim":
        result = coord.claim_task(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 3 and sys.argv[1] == "done":
        result = coord.complete_task(sys.argv[2], " ".join(sys.argv[3:]))
        print(json.dumps(result, indent=2))
    else:
        coord.check_in()
        print(f"\nUsage: python3 coordination.py checkin|claim <id> <desc>|done <id> <result>")
