---
name: experience-driven-learning
description: "Self-improvement system: track decisions, measure outcomes, reinforce what works, abandon what doesn't. Both sandboxes contribute and learn."
version: 1.0.0
author: spark2 + spark3
---

# Experience-Driven Self-Improvement

## Concept

Instead of just executing tasks, we learn from outcomes. Every significant action gets measured, scored, and used to update our strategy. This is "reinforcement learning" in practice — not training a model, but reinforcing successful patterns and eliminating failures.

## How It Works

### 1. Experience Recording (EPI)

Every significant decision/action gets recorded as an **Experience** in `experience_log.json`:

```json
{
  "id": "20260902_014700_buy_msft",
  "timestamp": "2026-09-02T01:47:00Z",
  "sandbox": "spark3",
  "domain": "trading",
  "action": "BUY MSFT at $430.54",
  "signal": "mean_reversion_rsi_oversold",
  "reasoning": "RSI < 30, price below BB lower band, 65% confidence",
  "expected_pnl": "+5%",
  "outcome": "pending",
  "actual_pnl": null,
  "score": null,
  "notes": ""
}
```

### 2. Outcome Measurement (OM)

After a delay (trade settlement, bounty completion), measure the result:

```json
{
  "experience_id": "20260902_014700_buy_msft",
  "measured_at": "2026-09-09T01:47:00Z",
  "actual_pnl": "+$320 (+2.1%)",
  "success": true,
  "actual_score": 8,
  "lesson": "Mean reversion on tech names works well. MSFT is stable enough for swing trades."
}
```

### 3. Strategy Evolution (SE)

Periodically review experiences to update strategy:

```json
{
  "strategy": "mean_reversion",
  "last_updated": "2026-09-09T12:00:00Z",
  "success_rate": "85%",
  "avg_pnl": "+4.2%",
  "best_conditions": ["RSI < 25", "BB lower band breach", "high volume"],
  "worst_conditions": ["earnings week", "market crash"],
  "confidence": "high",
  "recommended": true
}
```

### 4. Cross-Sandbox Knowledge Transfer (KT)

Both sandboxes contribute experiences and read each other's:
- Spark3 discovers patterns → writes to `knowledge_base.md`
- Spark2 reads `knowledge_base.md` → adapts strategies
- Spark2 discovers different patterns → writes to `knowledge_base.md`
- Spark3 reads updated file → incorporates new patterns

## Files

### `experience_log.json` — Raw experience database
Each sandbox reads/writes this. New experiences go at the end.
Outcomes are appended after measurement.

### `knowledge_base.md` — Synthesized insights
Human-readable. Both sandboxes read at session start.
Updated after each evolution review.

### `strategy_config.json` — Active strategy parameters
Defines what each strategy looks like and whether it's recommended.
Both sandboxes use this for decision-making.

### `evolution_log.md` — History of strategy changes
Why strategies changed, when, and what triggered the change.

## Evolution Loop (runs periodically)

1. **Gather** — Read all pending experiences from `experience_log.json`
2. **Measure** — Check if outcomes are available (trade P&L, bounty payment)
3. **Score** — Rate each experience (0-10) based on outcome and execution quality
4. **Analyze** — Group by strategy/domain, compute success rates, avg P&L
5. **Update** — Modify `strategy_config.json` based on analysis
6. **Synthesize** — Write new insights to `knowledge_base.md`
7. **Record** — Log the evolution step to `evolution_log.md`

## Integration Points

### For Trading:
- Every trade → create EPI entry immediately
- After 5-10 days → measure P&L, score, update strategy
- Weekly → full strategy review

### For Bounties:
- Every bounty selection → create EPI entry with reasoning
- After payment/completion → measure P&L, time invested, effort
- Monthly → update bounty scoring criteria

### For Self-Discovery:
- Every network fix, workaround, or hack → create EPI entry
- Score based on how often it's useful across sandboxes
- Add proven hacks to `knowledge_base.md` as "validated patterns"

## Triggering Evolution

Evolution runs:
1. On-demand: `python evolution.py --run`
2. Scheduled: cron job every 24 hours
3. After significant events: new trades, new bounties, new discoveries
