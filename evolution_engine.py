#!/usr/bin/env python3
"""
Experience-driven self-improvement system.
Both sandboxes log decisions, measure outcomes, and evolve together.

Usage:
    python evolution.py --record domain action reasoning expected --sandbox spark3
    python evolution.py --evolve                  # Analyze and update
    python evolution.py --status                  # Show current state
    python evolution.py --report                  # Full report
"""
import json, os, sys, re, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE_DIR = Path(__file__).parent
EXPERIENCE_LOG = "experience_log.json"
STRATEGY_CONFIG = "strategy_config.json"
KNOWLEDGE_BASE = "knowledge_base.md"
EVOLUTION_LOG = "evolution_log.json"


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


def load_or_create_strategies():
    """Load strategy config or create defaults."""
    config = read_json(STRATEGY_CONFIG, {})
    
    if "strategies" not in config or not config["strategies"]:
        config["strategies"] = {
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
            "network_fix": {
                "enabled": True,
                "success_rate": 0.0,
                "experience_count": 0,
                "avg_score": 0.0,
                "best_conditions": [],
                "worst_conditions": [],
                "recommended": True,
            },
            "bounty_hunt": {
                "enabled": True,
                "success_rate": 0.0,
                "experience_count": 0,
                "avg_score": 0.0,
                "best_conditions": [],
                "worst_conditions": [],
                "recommended": True,
            },
        }
        config["evolution_count"] = 0
    
    return config


def record_experience(domain, action, reasoning, expected_outcome, sandbox="spark3"):
    """Record a significant decision/action."""
    exp_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{domain}_{action[:20].replace(' ', '_')}"
    
    exp = {
        "id": exp_id,
        "timestamp": datetime.now().isoformat(),
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
    if isinstance(log, list):
        log.append(exp)
        write_json(EXPERIENCE_LOG, log)
    
    return exp_id


def record_outcome(experience_id, actual_result, score, notes=""):
    """Record the measured outcome of an experience."""
    outcome = {
        "experience_id": experience_id,
        "timestamp": datetime.now().isoformat(),
        "actual_result": actual_result,
        "score": score,
        "notes": notes,
    }
    
    log = read_json(EXPERIENCE_LOG, [])
    if isinstance(log, list):
        for exp in log:
            if isinstance(exp, dict) and exp.get("id") == experience_id:
                exp["outcome"] = actual_result
                exp["score"] = score
                exp["notes"] = notes
                break
        write_json(EXPERIENCE_LOG, log)


def run_evolution():
    """Run the evolution cycle: analyze experiences, update strategies, synthesize insights."""
    print("=" * 70)
    print(f"🧬 EVOLUTION CYCLE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    exp_log = read_json(EXPERIENCE_LOG, [])
    config = load_or_create_strategies()
    
    if not isinstance(exp_log, list) or not exp_log:
        print("No experiences to analyze. Record some first.")
        return
    
    # Group experiences by domain
    domain_stats = {}
    for exp in exp_log:
        if not isinstance(exp, dict):
            continue
            
        domain = exp.get("domain", "unknown")
        if domain not in domain_stats:
            domain_stats[domain] = {
                "total": 0,
                "completed": 0,
                "scores": [],
                "successful": 0,
                "total_pnl": 0.0,
                "examples": [],
            }
        domain_stats[domain]["total"] += 1
        
        if exp.get("outcome") != "pending" and exp.get("score") is not None:
            domain_stats[domain]["completed"] += 1
            score = exp["score"]
            if isinstance(score, (int, float)):
                domain_stats[domain]["scores"].append(score)
                
                if score >= 7:
                    domain_stats[domain]["successful"] += 1
                
                # Extract P&L if available
                result = str(exp.get("outcome", ""))
                if "$" in result:
                    try:
                        pnl_match = re.search(r'\$([+-]?[\d,]+\.?\d*)', result)
                        if pnl_match:
                            pnl = float(pnl_match.group(1).replace(',', ''))
                            domain_stats[domain]["total_pnl"] += pnl
                    except:
                        pass
                
                # Keep best/worst examples
                if len(domain_stats[domain]["examples"]) < 3:
                    domain_stats[domain]["examples"].append({
                        "id": exp["id"],
                        "action": exp.get("action", "")[:80],
                        "score": score,
                        "result": str(exp.get("outcome", ""))[:100],
                    })
    
    # Update strategy configs based on stats
    print(f"\n📊 Analysis results:")
    for domain_name, stats in domain_stats.items():
        if domain_name in config.get("strategies", {}):
            strat = config["strategies"][domain_name]
            
            if stats["completed"] > 0:
                success_rate = stats["successful"] / stats["completed"]
                avg_score = (sum(stats["scores"]) / len(stats["scores"])) if stats["scores"] else 0
                
                strat["success_rate"] = round(success_rate, 3)
                strat["experience_count"] = stats["completed"]
                strat["avg_score"] = round(avg_score, 2)
                
                # Update recommendation based on data
                if avg_score >= 7.0 and success_rate >= 0.7:
                    strat["recommended"] = True
                    if "high_confidence_signals" not in strat.get("best_conditions", []):
                        strat["best_conditions"] = ["high_confidence_signals", "favorable_market_conditions"]
                elif avg_score < 5.0 or success_rate < 0.4:
                    strat["recommended"] = False
                    if "low_volume" not in strat.get("worst_conditions", []):
                        strat["worst_conditions"] = ["low_volume", "volatile_markets"]
                
                status_icon = "🟢" if strat["recommended"] else "🔴"
                print(f"\n  {status_icon} {domain_name}:")
                print(f"     Experiences: {stats['completed']}")
                print(f"     Success rate: {success_rate:.0%}")
                print(f"     Avg score: {avg_score:.1f}/10")
                print(f"     Total P&L: ${stats['total_pnl']:,.2f}")
                print(f"     Recommended: {strat['recommended']}")
    
    # Save updated config
    config["evolution_count"] = config.get("evolution_count", 0) + 1
    write_json(STRATEGY_CONFIG, config)
    
    # Log evolution event
    evolution_entry = {
        "evolution_number": config["evolution_count"],
        "timestamp": datetime.now().isoformat(),
        "experiences_analyzed": len(exp_log),
        "domains_analyzed": len(domain_stats),
        "strategies_updated": len([d for d in domain_stats if d in config.get("strategies", {})]),
    }
    
    evolution_log = read_json(EVOLUTION_LOG, {"entries": []})
    if isinstance(evolution_log, dict) and "entries" in evolution_log:
        evolution_log["entries"].append(evolution_entry)
    else:
        evolution_log = {"entries": [evolution_entry]}
    write_json(EVOLUTION_LOG, evolution_log)
    
    # Synthesize insights into knowledge base
    insights = _synthesize_insights(domain_stats, config)
    
    print(f"\n✅ Evolution #{config['evolution_count']} complete")
    print(f"   Analyzed {len(exp_log)} experiences across {len(domain_stats)} domains")
    
    if insights:
        print(f"   💡 {len(insights)} insights synthesized")
        _save_knowledge_base(insights, config.get("evolution_count", 0))
    
    return config["evolution_count"]


def _synthesize_insights(domain_stats, config):
    """Generate human-readable insights from analysis."""
    insights = []
    
    for domain_name, stats in domain_stats.items():
        if stats["completed"] == 0:
            continue
        
        success_rate = stats["successful"] / stats["completed"] if stats["completed"] > 0 else 0
        avg_score = (sum(stats["scores"]) / len(stats["scores"])) if stats["scores"] else 0
        
        insights.append(f"\n### {domain_name.title()}")
        insights.append(f"- **Success rate:** {stats['successful']}/{stats['completed']} ({success_rate:.0%})")
        insights.append(f"- **Avg quality score:** {avg_score:.1f}/10")
        insights.append(f"- **Total P&L:** ${stats['total_pnl']:,.2f}")
        
        if stats["examples"]:
            best = max(stats["examples"], key=lambda x: x.get("score", 0))
            worst = min(stats["examples"], key=lambda x: x.get("score", 0))
            insights.append(f"- **Best example:** {best.get('action', 'N/A')} (score: {best.get('score', 'N/A')})")
            insights.append(f"- **Worst example:** {worst.get('action', 'N/A')} (score: {worst.get('score', 'N/A')})")
        
        # Generate recommendations
        if avg_score >= 8.0:
            insights.append(f"- **Recommendation:** ✅ Continue using {domain_name} — strong performance")
        elif avg_score >= 6.0:
            insights.append(f"- **Recommendation:** ⚠️ Use {domain_name} with caution — moderate performance")
        elif avg_score < 5.0:
            insights.append(f"- **Recommendation:** ❌ Consider pausing {domain_name} — weak performance")
    
    return insights


def _save_knowledge_base(insights, evolution_count):
    """Save insights to knowledge base."""
    kb_header = f"""# Knowledge Base — Self-Improvement System
## Auto-generated insights from experience-driven learning
## Last evolved: {datetime.now().strftime('%Y-%m-%d %H:%M')}
## Evolution count: {evolution_count}

"""
    kb_body = "\n".join(insights) if insights else "\n## No insights yet — more experiences needed\n"
    
    with open(Path(BASE_DIR) / KNOWLEDGE_BASE, 'w') as f:
        f.write(kb_header)
        f.write(kb_body)


def show_status():
    """Show current system state."""
    exp_log = read_json(EXPERIENCE_LOG, [])
    config = load_or_create_strategies()
    
    print("=" * 70)
    print("📊 SELF-IMPROVEMENT SYSTEM STATUS")
    print("=" * 70)
    
    if isinstance(exp_log, list):
        print(f"\n📝 Experiences: {len(exp_log)} total")
        pending = sum(1 for e in exp_log if isinstance(e, dict) and e.get("outcome") == "pending")
        print(f"⏳ Pending: {pending}")
        print(f"✅ Completed: {len(exp_log) - pending}")
    
    print(f"\n⚙️  Strategies:")
    for name, strat in config.get("strategies", {}).items():
        if isinstance(strat, dict):
            status_icon = "🟢" if strat.get("recommended", True) else "🔴"
            print(f"  {status_icon} {name:25s} | success: {strat.get('success_rate', 0):.0%} | "
                  f"experiences: {strat.get('experience_count', 0)} | "
                  f"avg_score: {strat.get('avg_score', 0):.1f}")
    
    print(f"\n🔄 Evolution count: {config.get('evolution_count', 0)}")


def show_report():
    """Generate full report."""
    exp_log = read_json(EXPERIENCE_LOG, [])
    config = load_or_create_strategies()
    
    print("=" * 70)
    print("📋 FULL SELF-IMPROVEMENT REPORT")
    print("=" * 70)
    
    if isinstance(exp_log, list):
        print(f"\n📝 Total Experiences: {len(exp_log)}")
        
        # By domain
        domains = {}
        for exp in exp_log:
            if not isinstance(exp, dict):
                continue
            d = exp.get("domain", "unknown")
            if d not in domains:
                domains[d] = {"total": 0, "completed": 0, "scores": []}
            domains[d]["total"] += 1
            if exp.get("outcome") != "pending" and exp.get("score") is not None:
                domains[d]["completed"] += 1
                if isinstance(exp.get("score"), (int, float)):
                    domains[d]["scores"].append(exp["score"])
        
        if domains:
            print(f"\n📊 By Domain:")
            for domain, stats in domains.items():
                avg_score = (sum(stats["scores"]) / len(stats["scores"])) if stats["scores"] else 0
                print(f"    {domain:20s}: {stats['total']} total, {stats['completed']} completed, avg_score: {avg_score:.1f}")
        
        # By sandbox
        sandboxes = {}
        for exp in exp_log:
            if not isinstance(exp, dict):
                continue
            s = exp.get("sandbox", "unknown")
            if s not in sandboxes:
                sandboxes[s] = {"total": 0, "completed": 0}
            sandboxes[s]["total"] += 1
            if exp.get("outcome") != "pending":
                sandboxes[s]["completed"] += 1
        
        if sandboxes:
            print(f"\n🌐 By Sandbox:")
            for sandbox, stats in sandboxes.items():
                print(f"    {sandbox:10s}: {stats['total']} total, {stats['completed']} completed")
    
    print(f"\n🔄 Evolution history: {config.get('evolution_count', 0)} cycles")
    
    # Print best/worst performers
    completed = [e for e in exp_log if isinstance(e, dict) and e.get("score") is not None]
    if completed:
        completed.sort(key=lambda x: x.get("score", 0), reverse=True)
        if len(completed) >= 3:
            print(f"\n🏆 Top 3 experiences:")
            for exp in completed[:3]:
                print(f"    ⭐ {exp['id']}: score={exp['score']}, action={exp.get('action', 'N/A')[:60]}")
            
            print(f"\n⚠️  Bottom 3 experiences:")
            for exp in completed[-3:]:
                print(f"    {exp['id']}: score={exp['score']}, action={exp.get('action', 'N/A')[:60]}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Experience-driven self-improvement")
    parser.add_argument("--init", action="store_true", help="Initialize the system")
    parser.add_argument("--run", action="store_true", help="Run one evolution cycle")
    parser.add_argument("--evolve", action="store_true", help="Run evolution cycle (alias for --run)")
    parser.add_argument("--status", action="store_true", help="Show current state")
    parser.add_argument("--report", action="store_true", help="Full report")
    parser.add_argument("--record", action="store_true", help="Record an experience")
    parser.add_argument("--domain", type=str, default="", help="Domain (trading, bounty, discovery)")
    parser.add_argument("--action", type=str, default="", help="Action taken")
    parser.add_argument("--reasoning", type=str, default="", help="Why this action was taken")
    parser.add_argument("--expected", type=str, default="", help="Expected outcome")
    parser.add_argument("--outcome", type=str, default="", help="Actual outcome")
    parser.add_argument("--score", type=float, default=0, help="Score 0-10")
    parser.add_argument("--sandbox", type=str, default="spark3", help="Sandbox identifier")
    
    args = parser.parse_args()
    
    if args.init:
        # Initialize system
        config = load_or_create_strategies()
        config["evolution_count"] = config.get("evolution_count", 0)
        write_json(STRATEGY_CONFIG, config)
        write_json(EXPERIENCE_LOG, [])
        write_json(EVOLUTION_LOG, {"entries": []})
        
        kb = f"""# Knowledge Base — Self-Improvement System
## Auto-generated insights from experience-driven learning
## Last evolved: {datetime.now().strftime('%Y-%m-%d %H:%M')}
## Evolution count: 0

## Current Strategies
- **Mean Reversion**: Default recommendation threshold 60% confidence
- **Momentum Breakout**: Default recommendation threshold 65% confidence
- **Volatility Breakout**: Default recommendation threshold 65% confidence

## Learnings
_No experiences recorded yet. Start trading or bounty hunting to build knowledge._
"""
        with open(Path(BASE_DIR) / KNOWLEDGE_BASE, 'w') as f:
            f.write(kb)
        
        print("✅ Self-improvement system initialized")
        print(f"   Strategy config: {STRATEGY_CONFIG}")
        print(f"   Experience log: {EXPERIENCE_LOG}")
        print(f"   Knowledge base: {KNOWLEDGE_BASE}")
    
    elif args.evolve or args.run:
        result = run_evolution()
        if result is None:
            print("No evolution performed.")
    
    elif args.status:
        show_status()
    
    elif args.report:
        show_report()
    
    elif args.record:
        if args.domain and args.action and args.reasoning and args.expected:
            exp_id = record_experience(
                args.domain, args.action, args.reasoning, args.expected, args.sandbox
            )
            print(f"✅ Experience recorded: {exp_id}")
        else:
            print("Usage: --record --domain X --action Y --reasoning Z --expected W")
            print("Example: --record --domain trading --action BUY_MSFT --reasoning 'RSI oversold' --expected '+5%'")
    
    elif args.outcome:
        if args.score:
            record_outcome(args.outcome, args.outcome, args.score)
            print(f"✅ Outcome recorded for: {args.outcome}")
        else:
            print("Usage: --outcome EXPERIENCE_ID --score N")
    
    else:
        print("Experience-driven self-improvement system")
        print("Usage:")
        print("  python evolution.py --init       # Initialize system")
        print("  python evolution.py --run        # Run evolution cycle")
        print("  python evolution.py --status     # Show state")
        print("  python evolution.py --report     # Full report")
