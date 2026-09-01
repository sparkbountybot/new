"""
Dashboard — Simple text-based dashboard for system status.
"""
from datetime import datetime


def simple_dashboard(trader=None, scanner=None, config=None):
    """Print a simple dashboard to stdout."""
    now = datetime.utcnow().isoformat()
    print(f"\n{'='*60}")
    print(f"  BOUNTYBOT FRAMEWORK v2")
    print(f"  {now} UTC")
    print(f"{'='*60}")

    # Trading status
    if trader:
        portfolio = trader.get_portfolio() if trader.is_connected else {"error": "Not connected"}
        print(f"\n  [TRADING]")
        if "error" not in portfolio:
            print(f"    Portfolio: ${portfolio.get('portfolio_value', 0):,.2f}")
            print(f"    Cash: ${portfolio.get('cash', 0):,.2f}")
            print(f"    Positions: {portfolio.get('num_positions', 0)}")
            positions = [p for p in portfolio.get("positions", []) if "error" not in p]
            for p in positions:
                pnl = p.get("unrealized_pl", 0)
                print(f"      {p['symbol']}: {p['qty']} @ ${p['avg_entry_price']:.2f} "
                      f"| ${p['current_price']:.2f} | P&L: ${pnl:,.2f}")
        else:
            print(f"    {portfolio['error']}")

    # Bounty status
    if scanner:
        summary = scanner.get_summary()
        print(f"\n  [BOUNTIES]")
        print(f"    Jobs found: {summary.get('total', 0)}")
        print(f"    High-value: {summary.get('high_value', 0)}")
        print(f"    Total potential: ${summary.get('total_reward', 0):,.2f}")
        jobs = scanner.state.get("jobs", [])[:5]
        for j in jobs:
            print(f"      {j['repo']}#{j['number']}: {j['title'][:60]} "
                  f"(${j['reward']}) [{j['difficulty']}]")

    print(f"\n{'='*60}")
