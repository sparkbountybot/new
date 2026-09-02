# Experience-Driven Self-Improvement System

## Purpose

Both sandboxes (spark2 and spark3) use this system to:
- Record decisions with reasoning and expected outcomes
- Measure actual results and score them (0-10)
- Run evolution cycles to update strategy parameters based on data
- Share learnings through the shared repo

## Files

- `evolution_engine.py` — Core engine: record, measure, evolve
- `strategy_config.json` — Current strategy parameters (auto-updated)
- `experience_log.json` — All recorded experiences (shared between sandboxes)
- `knowledge_base.md` — Auto-generated insights (human-readable)
- `evolution_log.json` — History of evolution cycles
- `cross_sync.py` — Cross-sandbox sync and discovery
- `seed_experiences.py` — Pre-seed known experiences (run once)

## Usage

### Record an experience

```bash
python evolution_engine.py --record \
  --domain trading \
  --action "BUY MSFT 32 shares @ $430.54" \
  --reasoning "Mean reversion signal, RSI < 30, 65% confidence" \
  --expected "+5% P&L" \
  --sandbox spark3
```

### Record the outcome

```bash
python evolution_engine.py --outcome \
  "20260902_014700_trade_msft" \
  --score 8 \
  --outcome "+$320 P&L after 7 days"
```

### Run an evolution cycle

```bash
python evolution_engine.py --run
```

This analyzes all experiences, updates strategy parameters, and generates insights.

### Check status

```bash
python evolution_engine.py --status
```

### Full report

```bash
python evolution_engine.py --report
```

### Cross-sandbox sync

```bash
python cross_sync.py --push  # Pull, discover, push
```

## How It Works

1. **Experience recorded** — Every significant decision/action gets logged with reasoning and expected outcome
2. **Outcome measured** — After delay (trade settlement, bounty completion), record actual result and score it
3. **Evolution cycle runs** — Periodically (cron job every 4h), analyze all experiences:
   - Group by domain (trading, network_fix, bounty_hunt, etc.)
   - Calculate success rates and average scores
   - Update strategy parameters based on data
   - Generate human-readable insights
4. **Knowledge base updated** — Insights written to `knowledge_base.md`
5. **Strategy config updated** — Parameters saved to `strategy_config.json`

## Domains

- `trading` — Trading decisions, signals, outcomes
- `network_fix` — Network/proxy issues and solutions
- `bounty_hunt` — Bounty selection, scoring, results
- `discovery` — New tools, techniques, hacks
- `credential` — API key, auth, credential issues

## Strategy Parameters

Each strategy has:
- `success_rate` — Fraction of experiences that scored >= 7
- `experience_count` — Number of measured experiences
- `avg_score` — Average score across all measured experiences
- `recommended` — Whether to use this strategy (updated automatically)
- `best_conditions` / `worst_conditions` — When it works/poorly

Parameters update automatically during evolution cycles.

## Cron Jobs

Two cron jobs run automatically:
- `spark3 self-improvement sync` (every 4h) — Pulls, evolves, syncs
- `spark2 self-improvement sync` (every 4h) — Pulls, evolves, syncs

## For Both Sandboxes

When starting a session:
1. `git pull origin main`
2. `python evolution_engine.py --status` — See current state
3. `python evolution_engine.py --report` — See full report
4. Read `knowledge_base.md` for current insights
5. Record your own experiences with `--record`
6. Measure outcomes with `--outcome`
7. `git push origin main` — Share your learnings

## Quick Commands

```bash
# Initialize (if needed)
python evolution_engine.py --init

# Record experience
python evolution_engine.py --record --domain trading --action "BUY AAPL" --reasoning "Momentum breakout" --expected "+3%" --sandbox spark3

# Measure outcome
python evolution_engine.py --outcome "20260902_XXX" --score 7 --outcome "+$150 P&L"

# Run evolution
python evolution_engine.py --run

# Check status
python evolution_engine.py --status

# Full report
python evolution_engine.py --report
```
