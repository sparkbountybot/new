#!/usr/bin/env python3
"""Cross-sandbox coordination — prevents duplicate work"""
import os, json, sys
from datetime import datetime, timezone

SHARED = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(SHARED, "work_items.json")

def get_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            return json.load(f)
    return {"tasks": [], "last_sync": None}

def save_tasks(data):
    data["last_sync"] = datetime.now(timezone.utc).isoformat()
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def claim(task_id, desc):
    data = get_tasks()
    for t in data["tasks"]:
        if t["task_id"] == task_id:
            if t["status"] == "done":
                return {"action": "skip", "reason": "already done"}
            if t["status"] == "running" and t["claimed_by"] != my_id:
                return {"action": "skip", "reason": "running in " + t["claimed_by"]}
            if t["status"] == "running":
                return {"action": "continue", "reason": "already claimed by me"}
    task = {"task_id": task_id, "description": desc, "status": "running", "claimed_by": my_id, "claimed_at": datetime.now(timezone.utc).isoformat(), "result": None}
    data["tasks"].append(task)
    save_tasks(data)
    return {"action": "claimed"}

def complete(task_id, result):
    data = get_tasks()
    for t in data["tasks"]:
        if t["task_id"] == task_id and t["claimed_by"] == my_id:
            t["status"] = "done"
            t["completed_at"] = datetime.now(timezone.utc).isoformat()
            t["result"] = result
            save_tasks(data)
            return {"action": "done"}
    return {"action": "not_found"}

def check_in():
    data = get_tasks()
    tasks = data.get("tasks", [])
    my = [t for t in tasks if t["status"] == "running" and t["claimed_by"] == my_id]
    theirs = [t for t in tasks if t["status"] == "running" and t["claimed_by"] != my_id]
    done = [t for t in tasks if t["status"] == "done"]
    print("CHECK-IN: " + my_id)
    if my:
        for t in my: print("  ME: " + t["task_id"] + " - " + t["description"])
    if theirs:
        for t in theirs: print("  THEM: " + t["task_id"] + " - " + t["description"])
    if done:
        for t in done[-5:]: print("  DONE: " + t["task_id"])

if __name__ == "__main__":
    my_id = sys.argv[1] if len(sys.argv) > 1 else "spark3"
    cmd = sys.argv[2] if len(sys.argv) > 2 else "checkin"
    if cmd == "checkin":
        check_in()
    elif cmd == "claim":
        print(json.dumps(claim(sys.argv[3], sys.argv[4]), indent=2))
    elif cmd == "done":
        print(json.dumps(complete(sys.argv[3], " ".join(sys.argv[4:])), indent=2))
