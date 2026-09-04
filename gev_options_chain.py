#!/usr/bin/env python3
"""
Synthetic GEV Options Chain Generator
Mimics market maker behavior on a micro-cap with wide spreads
Uses our greeks calculator + realistic order book model
"""
import math
import random
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
import sys
sys.path.insert(0, '/sandbox/new')
from options_greeks import GreeksCalculator


class GevOptionsMarket:
    """Simulates a realistic GEV options market with wide spreads, low liquidity"""

    BASE_PRICE = 10.00  # Approximate GEV price
    SPREAD_FACTOR = 1.50  # 150% bid-ask spread (realistic for illiquid microcap)
    IV_BIAS = 0.90  # High IV typical of illiquid microcap
    MIN_SPREAD = 0.10  # Min $0.10 spread
    LIQUIDITY_BIAS = {
        0: 0.8,    # Deep ITM: moderate
        1: 0.5,    # ITM: low
        2: 1.0,    # ATM: baseline
        3: 0.5,    # OTM: low
        4: 0.3,    # Deep OTM: very low
    }
    EXPIRY_DATES = [7, 14, 30, 45, 60, 90]
    OPEN_INTEREST_BIAS = {0: 0.2, 1: 0.5, 2: 1.0, 3: 0.5, 4: 0.2}  # Peaks at ATM

    def __init__(self, spot: Optional[float] = None, iv: Optional[float] = None):
        self.spot = spot or self.BASE_PRICE
        self.iv = iv or self.IV_BIAS
        self.seed = int(datetime.now(timezone.utc).timestamp())

    def set_spot(self, price: float):
        """Simulate price movement"""
        self.spot = price

    def get_strike(self, moneyness: int) -> float:
        """Get strike price for moneyness level"""
        if moneyness == 0:
            return round(self.spot * 0.75)
        elif moneyness == 1:
            return round(self.spot * 0.90)
        elif moneyness == 2:
            return round(self.spot)
        elif moneyness == 3:
            return round(self.spot * 1.10)
        elif moneyness == 4:
            return round(self.spot * 1.25)

    def get_bid_ask(self, mid: float, liquidity: float = 1.0) -> tuple:
        """Get bid and ask from mid price with spread"""
        spread = max(mid * self.SPREAD_FACTOR, 0.05)  # Min $0.05 spread
        half = spread / 2.0
        bid = max(mid - half, 0.01)
        ask = mid + half
        # Adjust for liquidity
        liq = self.LIQUIDITY_BIAS.get(max(0, min(4, int(round(abs(liquidity - 2))))), 1.0)
        bid = bid * liq  # Bid drops with liquidity
        return round(bid, 2), round(ask, 2)

    def generate_chain(self, expiry_days: int) -> list:
        """Generate options chain for a given expiry"""
        T = expiry_days / 365.0
        r = 0.05
        chain = []

        for moneyness in range(5):
            strike = self.get_strike(moneyness)
            liq = self.LIQUIDITY_BIAS[moneyness]

            for opt_type in ['call', 'put']:
                mid = GreeksCalculator.calculate(
                    self.spot, strike, T, r, self.iv, opt_type
                ).price

                bid, ask = self.get_bid_ask(mid, liq)
                oi = int(self.OPEN_INTEREST_BIAS[moneyness] * 100 * liq)

                mid_price = (bid + ask) / 2.0
                greeks = GreeksCalculator.calculate(
                    self.spot, strike, T, r, self.iv, opt_type
                )

                contract = {
                    'symbol': f'GEV{expiry_days:02d}{self._expiry_code(expiry_days)}{self._option_code(strike, opt_type)}',
                    'strike': strike,
                    'type': opt_type,
                    'bid': bid,
                    'ask': ask,
                    'mid': mid_price,
                    'open_interest': oi,
                    'greeks': {
                        'delta': greeks.delta,
                        'gamma': greeks.gamma,
                        'theta': greeks.theta,
                        'vega': greeks.vega,
                    }
                }
                chain.append(contract)

        return chain

    def _expiry_code(self, days: int) -> str:
        months = {7: 'C', 14: 'D', 30: 'F', 45: 'G', 60: 'H', 90: 'U'}
        return months.get(days, 'F')

    def _option_code(self, strike: float, opt_type: str) -> str:
        code = 'C' if opt_type == 'call' else 'P'
        return f'{int(strike * 10)}{code}'

    def get_full_chain(self, expiries: Optional[list] = None) -> dict:
        """Generate complete options chain"""
        expiries = expiries or self.EXPIRY_DATES
        result = {'spot': self.spot, 'iv': self.iv, 'chains': {}}

        for exp in expiries:
            result['chains'][exp] = self.generate_chain(exp)

        return result

    def simulate_price(self, steps: int = 10) -> list:
        """Simulate price path for backtesting"""
        prices = [self.spot]
        for _ in range(steps):
            change = random.gauss(0, self.spot * 0.03)  # 3% daily move
            self.spot = max(0.50, self.spot + change)
            prices.append(round(self.spot, 2))
        return prices


def demo():
    """Generate and display GEV options chain"""
    market = GevOptionsMarket(spot=10.00, iv=0.90)
    chain = market.get_full_chain([7, 14, 30])

    print(f"GEV Options Chain Generator — Spot: ${market.spot} | IV: {market.iv*100:.0f}%\n")

    for exp, contracts in chain['chains'].items():
        print(f"=== {exp} days to expiry ===")
        print(f"{'Strike':>8} | {'Type':>4} | {'Bid':>6} | {'Ask':>6} | {'Mid':>6} | {'OI':>4}")
        print("-" * 55)
        for c in sorted(contracts, key=lambda x: x['strike']):
            print(f"${c['strike']:>6.1f} | {c['type']:>4} | ${c['bid']:>5.2f} | ${c['ask']:>5.2f} | ${c['mid']:>5.2f} | {c['open_interest']:>4}")
        print()


if __name__ == "__main__":
    demo()
