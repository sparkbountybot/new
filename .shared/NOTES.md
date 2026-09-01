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
- Last sync: never (initial commit)
- Both instances: share this repo
- Git auth: stored in credential helper

## Setup for each sandbox
```bash
cd /path/to/sandbox/new
mkdir -p .shared/notes .shared/sessions .shared
cp /path/to/BASE/.shared/NOTES.md .shared/  # if copying first time
git add .shared/
git commit -m "Add shared notes structure"
git push
```
