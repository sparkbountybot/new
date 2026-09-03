#!/usr/bin/env python3
"""
Spark Coordination — prevents duplicate work between sandboxes
Run from either sandbox: python3 sync_protocol.py
"""
import os
import json
from datetime import datetime, timezone

SHARED_DIR = os.path.join(os.path.dirname(__file__), ".github", "shared")
WORK_ITEM_FILE = os.path.join(SHARED_DIR, "work_items.json")


class WorkCoordination:
    """Prevents both sandboxes from doing the same work"""

    def __init__(self, sandbox_id="spark2"):
        self.id = sandbox_id
        self.dir = SHARED_DIR
        os.makedirs(self.dir, exist_ok=True)

    def get_work_items(self):
        if os.path.exists(WORK_ITEM_FILE):
            with open(WORK_ITEM_FILE) as f:
                return json.load(f)
        return {"items": [], "last_updated": None}

    def claim_task(self, task_id, description, duration_minutes=10):
        items = self.get_work_items()

        for item in items["items"]:
            if item["task_id"] == task_id:
                if item["status"] == "done":
                    return {"action": "skip", "reason": "already done"}
                elif item["status"] == "running" and item["claimed_by"] == self.id:
                    return {"action": "continue", "reason": "already claimed by me"}
                elif item["status"] == "running":
                    return {"action": "skip", "reason": "running in " + item["claimed_by"], "other_sandbox": item["claimed_by"]}
                elif item["status"] == "done":
                    return {"action": "skip", "reason": "already done"}

        item = {
            "task_id": task_id,
            "description": description,
            "status": "running",
            "claimed_by": self.id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "estimated_minutes": duration_minutes,
            "result": None
        }
        items["items"].append(item)
        items["last_updated"] = datetime.now(timezone.utc).isoformat()

        with open(WORK_ITEM_FILE, 'w') as f:
            json.dump(items, f, indent=2)

        print("  [CLAIMED] " + task_id + ": " + description)
        return {"action": "claimed", "reason": "task claimed"}

    def complete_task(self, task_id, result_summary):
        items = self.get_work_items()
        for item in items["items"]:
            if item["task_id"] == task_id:
                item["status"] = "done"
                item["completed_at"] = datetime.now(timezone.utc).isoformat()
                item["result"] = result_summary
                items["last_updated"] = datetime.now(timezone.utc).isoformat()

                with open(WORK_ITEM_FILE, 'w') as f:
                    json.dump(items, f, indent=2)

                print("  [DONE] " + task_id + ": " + result_summary[:60])
                return True

        print("  [ERROR] Task " + task_id + " not found")
        return False

    def list_active_tasks(self):
        items = self.get_work_items()
        print("\n--- Active Tasks (" + self.id + ") ---")
        print("Last updated: " + str(items.get("last_updated", "never")))

        if not items["items"]:
            print("  (no tasks yet)")
            return

        for item in items["items"][-10:]:
            status_icon = {"pending": "o", "running": "x", "done": "+", "abandoned": "-"}
            icon = status_icon.get(item["status"], "?")
            who = item["claimed_by"]
            ts = item.get("claimed_at", "")[:16]
            desc = item["description"][:60]
            print("  " + icon + " [" + who + "] " + item["task_id"] + " | " + desc)
            if item["status"] == "running":
                print("     started: " + ts)
            elif item.get("result"):
                print("     result: " + item["result"][:80])


if __name__ == "__main__":
    import sys
    cwd = os.getcwd()
    if "spark2" in cwd.lower():
        sandbox = "spark2"
    elif "spark3" in cwd.lower():
        sandbox = "spark3"
    else:
        sandbox = "spark2"

    wc = WorkCoordination(sandbox)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "list":
            wc.list_active_tasks()
        elif cmd == "claim" and len(sys.argv) > 3:
            result = wc.claim_task(sys.argv[2], sys.argv[3])
            print("Result: " + json.dumps(result))
        elif cmd == "done" and len(sys.argv) > 2:
            result = wc.complete_task(sys.argv[2], " ".join(sys.argv[3:]))
            print("Result: " + json.dumps({"success": result}))
        elif cmd == "check":
            wc.list_active_tasks()
        else:
            print("Usage: python3 sync.py <list|claim <id> <desc>|done <id> <result>|check>")
    else:
        wc.list_active_tasks()
        print("\nSync check-in complete at " + datetime.now(timezone.utc).strftime("%H:%M"))
