#!/usr/bin/env python3
"""
Experience-driven self-improvement system.

Both sandboxes contribute to a shared experience log.
Periodic evolution reviews analyze outcomes and update strategies.

Usage:
    python evolution.py --record domain action reason expected --outcome outcome --score score
    python evolution.py --evolve       # Run evolution cycle
    python evolution.py --status       # Show current strategy state
    python evolution.py --report       # Full report of experiences + insights
"""
import json, os, sys, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

UTC_NOW = lambda: datetime.now(tz=None)  # Keep existing behavior, suppress deprecation

BASE_DIR = Path(__file__).parent

def read_json(path, default=None):
    """Read JSON file, return default if missing."""
    p = Path(BASE_DIR) / path
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default if default is not None else {}

def write_json(path, data):
    """Write data as JSON."""
    p = Path(BASE_DIR) / path
    with open(p, 'w') as f:
        json.dump(data, f, indent=2)

def append_json_list(path, item):
    """Append item to a JSON list file, creating if needed."""
    data = read_json(path, [])
    if isinstance(data, list):
        data.append(item)
        write_json(path, data)
    return data

# === DATA FILES ===
EXPERIENCE_LOG = "experience_log.json"        # Raw experiences
OUTCOMES_LOG = "outcomes_log.json"             # Measured outcomes
STRATEGY_CONFIG = "strategy_config.json"       # Active strategy parameters
KNOWLEDGE_BASE = "knowledge_base.md"           # Synthesized insights
EVOLUTION_LOG = "evolution_log.md"             # History of strategy changes

# === EXPERIENCE RECORDING ===
def record_experience(domain, action, reasoning, expected_outcome, sandbox="unknown"):
    """Record a significant decision/Action."""
    exp = {
        "id": f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{domain}_{action[:20].replace(' ', '_')}",
        "timestamp": datetime.utcnow().isoformat(),
        "sandbox": sandbox,
        "domain": domain,
        "action": action,
        "reasoning": reasoning,
        "expected_outcome": expected_outcome,
        "outcome": "pending",
        "actual_result": None,
        "score": None,
        "notes": "",
    }
    
    log = read_json(EXPERIENCE_LOG, [])
    log.append(exp)
    write_json(EXPERIENCE_LOG, log)
    
    print(f"✅ Experience recorded: {exp['id']}")
    print(f"   Domain: {domain}")
    print(f"   Action: {action[:60]}")
    return exp

# === OUTCOME MEASUREMENT ===
def record_outcome(experience_id, actual_result, score, notes="", timestamp=None):
    """Record the measured outcome of an experience."""
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat()
    
    outcome = {
        "experience_id": experience_id,
        "timestamp": timestamp,
        "actual_result": actual_result,
        "score": score,
        "notes": notes,
    }
    
    log = read_json(OUTCOMES_LOG, [])
    log.append(outcome)
    write_json(OUTCOMES_LOG, log)
    
    # Update the experience in the log too
    exp_log = read_json(EXPERIENCE_LOG, [])
    for exp in exp_log:
        if exp.get("id") == experience_id:
            exp["outcome"] = actual_result
            exp["score"] = score
            exp["notes"] = notes
            break
    write_json(EXPERIENCE_LOG, exp_log)
    
    print(f"✅ Outcome recorded: {experience_id}")
    print(f"   Result: {actual_result[:80]}")
    print(f"   Score: {score}/10")
    return outcome

# === STRATEGY CONFIGURATION ===
def load_strategy_config():
    """Load current strategy configuration."""
    config = read_json(STRATEGY_CONFIG, {
        "strategies": {
            "mean_reversion": {
                "enabled": True,
                "confidence_threshold": 0.60,
                "success_rate": 0.0,
                "experience_count": 0,
                "avg_score": 0.0,
                "best_conditions": [],
                "worst_conditions": [],
                "recommended": True,
            },
            "momentum_breakout": {
                "enabled": True,
                "confidence_threshold": 0.65,
                "success_rate": 0.0,
                "experience_count": 0,
                "avg_score": 0.0,
                "best_conditions": [],
                "worst_conditions": [],
                "recommended": True,
            },
            "volatility_breakout": {
                "enabled": True,
                "confidence_threshold": 0.65,
                "success_rate": 0.0,
                "experience_count": 0,
                "avg_score": 0.0,
                "best_conditions": [],
                "worst_conditions": [],
                "recommended": True,
            },
        },
        "updated_at": "",
        "evolution_count": 0,
    })
    config["updated_at"] = datetime.utcnow().isoformat()
    return config

def save_strategy_config(config):
    """Save strategy configuration."""
    config["updated_at"] = datetime.utcnow().isoformat()
    write_json(STRATEGY_CONFIG, config)

# === EVOLUTION ENGINE ===
def evolve():
    """Run the evolution cycle: analyze experiences, update strategies, synthesize insights."""
    print("=" * 70)
    print("  🧬 SELF-IMPROVEMENT EVOLUTION")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    
    exp_log = read_json(EXPERIENCE_LOG, [])
    outcome_log = read_json(OUTCOMES_LOG, [])
    config = load_strategy_config()
    
    # Group experiences by domain + strategy
    strategy_stats = {}
    for exp in exp_log:
        domain = exp.get("domain", "unknown")
        if domain not in strategy_stats:
            strategy_stats[domain] = {
                "total": 0,
                "completed": 0,
                "scores": [],
                "successful": 0,
                "total_pnl": 0.0,
                "examples": [],
            }
        strategy_stats[domain]["total"] += 1
        
        if exp.get("outcome") != "pending" and exp.get("score") is not None:
            strategy_stats[domain]["completed"] += 1
            strategy_stats[domain]["scores"].append(exp["score"])
            
            if exp["score"] >= 7:
                strategy_stats[domain]["successful"] += 1
            
            # Extract P&L if available
            result = str(exp.get("outcome", ""))
            if "P&L" in result or "$" in result:
                try:
                    import re
                    pnl_match = re.search(r'\$([+-]?[\d,]+\.?\d*)', result)
                    if pnl_match:
                        pnl = float(pnl_match.group(1).replace(',', ''))
                        strategy_stats[domain]["total_pnl"] += pnl
                except:
                    pass
            
            # Keep best/worst examples
            if len(strategy_stats[domain]["examples"]) < 3:
                strategy_stats[domain]["examples"].append({
                    "id": exp["id"],
                    "action": exp["action"][:80],
                    "score": exp["score"],
                    "result": str(exp["outcome"])[:100],
                })
    
    # Update strategy configs based on stats
    for strategy_name, stats in strategy_stats.items():
        if strategy_name in config.get("strategies", {}):
            strat = config["strategies"][strategy_name]
            
            if stats["completed"] > 0:
                success_rate = stats["successful"] / stats["completed"]
                avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
                
                strat["success_rate"] = round(success_rate, 3)
                strat["experience_count"] = stats["completed"]
                strat["avg_score"] = round(avg_score, 2)
                
                # Update recommendation based on data
                if avg_score >= 7.0 and success_rate >= 0.7:
                    strat["recommended"] = True
                    strat["best_conditions"] = ["high_confidence_signals", "favorable_market_conditions"]
                elif avg_score < 5.0 or success_rate < 0.4:
                    strat["recommended"] = False
                    strat["worst_conditions"] = ["low_volume", "volatile_markets"]
                
                print(f"\n  📊 {strategy_name}:")
                print(f"     Experiences: {stats['completed']}")
                print(f"     Success rate: {success_rate:.0%}")
                print(f"     Avg score: {avg_score:.1f}/10")
                print(f"     Total P&L: ${stats['total_pnl']:,.2f}")
                print(f"     Recommended: {strat['recommended']}")
    
    # Save updated config
    config["evolution_count"] = config.get("evolution_count", 0) + 1
    save_strategy_config(config)
    
    # Synthesize insights into knowledge base
    insights = []
    for domain, stats in strategy_stats.items():
        if stats["completed"] > 0:
            avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
            insights.append(f"\n### {domain.title()}")
            insights.append(f"- **Success rate:** {stats['successful']}/{stats['completed']} ({stats['successful']/max(stats['completed'],1):.0%})")
            insights.append(f"- **Avg quality score:** {avg_score:.1f}/10")
            insights.append(f"- **Total P&L:** ${stats['total_pnl']:,.2f}")
            if stats["examples"]:
                best = max(stats["examples"], key=lambda x: x["score"])
                worst = min(stats["examples"], key=lambda x: x["score"])
                insights.append(f"- **Best example:** {best['action']} (score: {best['score']})")
                insights.append(f"- **Worst example:** {worst['action']} (score: {worst['score']})")
    
    # Update knowledge base
    kb_header = f"""# Knowledge Base — Self-Improvement System
## Auto-generated insights from experience-driven learning
## Last evolved: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
## Evolution count: {config.get('evolution_count', 0)}

"""
    kb_body = "\n".join(insights) if insights else "\n## No experiences recorded yet\n\n"
    
    with open(Path(BASE_DIR) / KNOWLEDGE_BASE, 'w') as f:
        f.write(kb_header)
        f.write(kb_body)
    
    # Log evolution event
    evolution_entry = f"\n### Evolution #{config['evolution_count']} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n"
    evolution_entry += f"- Experiences analyzed: {len(exp_log)}\n"
    evolution_entry += f"- Strategies updated: {len(strategy_stats)}\n"
    evolution_entry += f"- New insights: {len(insights)}\n"
    
    evolution_log = read_json(EVOLUTION_LOG, {"entries": []})
    evolution_log["entries"].append({
        "evolution_number": config["evolution_count"],
        "timestamp": datetime.utcnow().isoformat(),
        "experiences_analyzed": len(exp_log),
        "strategies_updated": len(strategy_stats),
        "insights_count": len(insights),
    })
    write_json(EVOLUTION_LOG, evolution_log)
    
    print(f"\n  ✅ Evolution #{config['evolution_count']} complete")
    print(f"  📊 Analyzed {len(exp_log)} experiences")
    print(f"  📈 Updated {len(strategy_stats)} strategy parameters")
    print(f"  💡 {len(insights)} new insights synthesized")
    
    return {
        "evolution_number": config["evolution_count"],
        "experiences_analyzed": len(exp_log),
        "strategies_updated": len(strategy_stats),
        "insights": insights,
    }

# === STATUS / REPORTING ===
def status():
    """Show current system state."""
    exp_log = read_json(EXPERIENCE_LOG, [])
    outcome_log = read_json(OUTCOMES_LOG, [])
    config = load_strategy_config()
    
    print("=" * 70)
    print("  📊 SELF-IMPROVEMENT SYSTEM STATUS")
    print("=" * 70)
    
    print(f"\n  📝 Experiences: {len(exp_log)} total")
    pending = sum(1 for e in exp_log if e.get("outcome") == "pending")
    print(f"  ⏳ Pending: {pending}")
    print(f"  ✅ Completed: {len(exp_log) - pending}")
    
    print(f"\n  📈 Outcomes measured: {len(outcome_log)}")
    
    print(f"\n  ⚙️  Strategies:")
    for name, strat in config.get("strategies", {}).items():
        status_icon = "🟢" if strat.get("recommended", True) else "🔴"
        print(f"    {status_icon} {name:25s} | success: {strat.get('success_rate', 0):.0%} | "
              f"experiences: {strat.get('experience_count', 0)} | "
              f"avg_score: {strat.get('avg_score', 0):.1f}")
    
    print(f"\n  🔄 Evolution count: {config.get('evolution_count', 0)}")
    
    # Print recent experiences
    if exp_log:
        print(f"\n  📋 Recent experiences:")
        for exp in exp_log[-5:]:
            status_icon = "⏳" if exp.get("outcome") == "pending" else f"⭐{exp.get('score', '?')}"
            print(f"    {status_icon} {exp['id']} | {exp['action'][:60]}")

def report():
    """Generate full report."""
    exp_log = read_json(EXPERIENCE_LOG, [])
    outcome_log = read_json(OUTCOMES_LOG, [])
    config = load_strategy_config()
    
    print("=" * 70)
    print("  📋 FULL SELF-IMPROVEMENT REPORT")
    print("=" * 70)
    
    print(f"\n  📝 Total Experiences: {len(exp_log)}")
    
    # By domain
    domains = {}
    for exp in exp_log:
        d = exp.get("domain", "unknown")
        domains.setdefault(d, {"total": 0, "completed": 0, "scores": []})
        domains[d]["total"] += 1
        if exp.get("outcome") != "pending":
            domains[d]["completed"] += 1
            if exp.get("score"):
                domains[d]["scores"].append(exp["score"])
    
    print(f"\n  📊 By Domain:")
    for domain, stats in domains.items():
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        print(f"    {domain:20s}: {stats['total']} total, {stats['completed']} completed, avg_score: {avg_score:.1f}")
    
    # By sandbox
    sandboxes = {}
    for exp in exp_log:
        s = exp.get("sandbox", "unknown")
        sandboxes.setdefault(s, {"total": 0, "completed": 0})
        sandboxes[s]["total"] += 1
        if exp.get("outcome") != "pending":
            sandboxes[s]["completed"] += 1
    
    print(f"\n  🌐 By Sandbox:")
    for sandbox, stats in sandboxes.items():
        print(f"    {sandbox:10s}: {stats['total']} total, {stats['completed']} completed")
    
    print(f"\n  🔄 Evolution history: {config.get('evolution_count', 0)} cycles")
    
    # Print best performers
    completed = [e for e in exp_log if e.get("score") is not None]
    if completed:
        completed.sort(key=lambda x: x.get("score", 0), reverse=True)
        print(f"\n  🏆 Top 5 experiences:")
        for exp in completed[:5]:
            print(f"    {exp['id']}: score={exp['score']}, action={exp['action'][:60]}")
    
    # Print worst performers
    if len(completed) >= 5:
        print(f"\n  ⚠️  Bottom 5 experiences:")
        for exp in completed[-5:]:
            print(f"    {exp['id']}: score={exp['score']}, action={exp['action'][:60]}")

# === CLI ===
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Experience-driven self-improvement")
    parser.add_argument("--record", action="store_true", help="Record an experience")
    parser.add_argument("--domain", type=str, help="Domain (trading, bounty, discovery, etc.)")
    parser.add_argument("--action", type=str, help="Action taken")
    parser.add_argument("--reasoning", type=str, help="Why this action was taken")
    parser.add_argument("--expected", type=str, help="Expected outcome")
    parser.add_argument("--outcome", type=str, help="Actual outcome (for measuring)")
    parser.add_argument("--score", type=float, help="Score 0-10 (for measuring)")
    parser.add_argument("--evolve", action="store_true", help="Run evolution cycle")
    parser.add_argument("--status", action="store_true", help="Show current state")
    parser.add_argument("--report", action="store_true", help="Full report")
    parser.add_argument("--sandbox", type=str, default="spark3", help="Sandbox identifier")
    
    args = parser.parse_args()
    
    if args.evolve:
        evolve()
    elif args.status:
        status()
    elif args.report:
        report()
    elif args.record:
        record_experience(args.domain, args.action, args.reasoning, args.expected, args.sandbox)
    elif args.outcome:
        # Need experience_id somehow — for now, print instructions
        print("To record an outcome, use: --record first, then --evolve")
        print("Or manually add to experience_log.json")
        record_outcome("manual", args.outcome, args.score or 0, "manual")
    else:
        print("Self-improvement system")
        print("Usage:")
        print("  python evolution.py --record --domain trading --action 'BUY MSFT' --reasoning 'RSI oversold' --expected '+5%'")
        print("  python evolution.py --evolve      # Analyze and update")
        print("  python evolution.py --status      # Show state")
        print("  python evolution.py --report      # Full report")
