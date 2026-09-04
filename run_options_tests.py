#!/usr/bin/env python3
"""GEV Options Strategy Runner — tests multiple strategies across spot prices"""
import json, random
import sys
sys.path.insert(0, '/sandbox/new')
from paper_options_engine import OptionsStrategyTester

def run_comprehensive_test():
    """Test credit put spreads across different spot prices"""
    base_spot = 10.00
    runs = 100
    
    results = {'put_spreads': [], 'iron_condors': [], 'stats': {}}
    
    # Credit Put Spread analysis
    spread_results = []
    for i in range(runs):
        tester = OptionsStrategyTester(50000)
        result = tester.run_credit_put_spread(base_spot, 30)
        if 'error' not in result:
            # Random expiry: -15% to +15%
            change = random.gauss(0, 0.05)  # 5% daily vol
            expiry_spot = max(0.50, base_spot * (1 + change * 3))
            pnl = tester.simulate_expiry(expiry_spot)
            spread_results.append({
                'expiry_spot': round(expiry_spot, 2),
                'pnl': pnl,
                'credit': result['net_credit']
            })
    
    wins = [r for r in spread_results if r['pnl'] > 0]
    losses = [r for r in spread_results if r['pnl'] < 0]
    
    results['stats']['credit_put_spread'] = {
        'total_runs': len(spread_results),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': f"{len(wins)/len(spread_results)*100:.1f}%",
        'avg_win': f"${sum(r['pnl'] for r in wins)/len(wins):.2f}" if wins else "$0.00",
        'avg_loss': f"${sum(r['pnl'] for r in losses)/len(losses):.2f}" if losses else "$0.00",
        'total_pnl': f"${sum(r['pnl'] for r in spread_results):.2f}",
        'total_credits': f"${sum(r['credit'] for r in spread_results):.2f}"
    }
    
    # Iron Condor analysis
    condor_results = []
    for i in range(runs):
        tester = OptionsStrategyTester(50000)
        result = tester.run_iron_condor(base_spot, 30)
        if 'error' not in result:
            change = random.gauss(0, 0.05)
            expiry_spot = max(0.50, base_spot * (1 + change * 3))
            pnl = tester.simulate_expiry(expiry_spot)
            condor_results.append({
                'expiry_spot': round(expiry_spot, 2),
                'pnl': pnl,
                'credit': result['total_credit']
            })
    
    wins_c = [r for r in condor_results if r['pnl'] > 0]
    losses_c = [r for r in condor_results if r['pnl'] < 0]
    
    results['stats']['iron_condor'] = {
        'total_runs': len(condor_results),
        'wins': len(wins_c),
        'losses': len(losses_c),
        'win_rate': f"{len(wins_c)/len(condor_results)*100:.1f}%",
        'avg_win': f"${sum(r['pnl'] for r in wins_c)/len(wins_c):.2f}" if wins_c else "$0.00",
        'avg_loss': f"${sum(r['pnl'] for r in losses_c)/len(losses_c):.2f}" if losses_c else "$0.00",
        'total_pnl': f"${sum(r['pnl'] for r in condor_results):.2f}",
        'total_credits': f"${sum(r['credit'] for r in condor_results):.2f}"
    }
    
    return results


def print_report(results):
    print(f"\n=== GEV OPTIONS STRATEGY REPORT ===\n")
    
    for strategy, stats in results['stats'].items():
        name = strategy.replace('_', ' ').title()
        print(f"--- {name} ---")
        print(f"  Runs: {stats['total_runs']}")
        print(f"  Win Rate: {stats['win_rate']}")
        print(f"  Avg Win: {stats['avg_win']}")
        print(f"  Avg Loss: {stats['avg_loss']}")
        print(f"  Total P&L: {stats['total_pnl']}")
        print(f"  Total Credits Collected: {stats['total_credits']}")
        print()


if __name__ == "__main__":
    results = run_comprehensive_test()
    print_report(results)
    
    # Save results
    with open('/sandbox/new/gev_options_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Results saved to gev_options_results.json")
