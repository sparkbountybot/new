# Shared Knowledge Base — spark2 ↔ spark3

## How it works
Both sandbox instances (spark2 and spark3) read/write markdown files in `.shared/` to share context across sessions.

## Structure
- `notes/current.md` - Active notes (both read at start, write updates)
- `sessions/spark2.md` - Spark2 session history
- `sessions/spark3.md` - Spark3 session history
- `decisions.md` - Key decisions made by either instance

## Usage
Each instance should:
1. Read `.shared/notes/current.md` on startup
2. Write updates after significant work
3. git push after each update

## Current State
- Last sync: 2026-09-01
- Both instances: share repo `sparkbountybot/new`
- Git auth: stored in credential helper

## Setup for each sandbox
```bash
# In spark2 or spark3:
mkdir -p /sandbox/new/.shared/{notes,sessions}
echo "# Shared Notes" > /sandbox/new/.shared/notes/current.md
cd /sandbox/new && git add .shared/ && git commit -m "init shared notes" && git push
```
