#!/usr/bin/env python3
"""Paper options engine for GEV — tests strategies against synthetic chain"""
import json, os, random
from datetime import datetime, timezone
from typing import Optional, Dict, List
import sys
sys.path.insert(0, '/sandbox/new')
from gev_options_chain import GevOptionsMarket

class PaperOptionsAccount:
    def __init__(self, equity: float = 50000):
        self.equity = equity
        self.cash = equity * 0.7  # 70% cash reserve
        self.positions: Dict[str, dict] = {}  # contract_id -> position info
        self.trades: List[dict] = []
        self.max_risk_per_trade = equity * 0.05  # 5% equity max loss per trade

    def get_available(self):
        """Available cash after margin for spreads"""
        return self.cash

    def check_risk(self, cost: float, potential_loss: float):
        if potential_loss > self.max_risk_per_trade:
            return False, f"Risk ${potential_loss:.0f} exceeds {self.max_risk_per_trade:.0f} limit"
        if cost > self.get_available():
            return False, f"Cost ${cost:.0f} exceeds ${self.get_available():.0f} available"
        return True, "OK"

    def buy_leg(self, contract: dict, cost: float, premium: float):
        """Buy one leg of an options spread"""
        key = f"{contract['symbol']}_BUY"
        self.positions[key] = {
            'action': 'BUY', 'contract': contract, 'premium': premium,
            'cost': cost, 'qty': 1, 'entry_time': datetime.now(timezone.utc).isoformat(),
            'status': 'open'
        }
        self.cash -= cost
        self.trades.append({
            'ts': datetime.now(timezone.utc).isoformat(), 'action': 'BUY',
            'symbol': contract['symbol'], 'strike': contract['strike'],
            'type': contract['type'], 'premium': premium, 'cost': cost,
            'spot': contract.get('spot')
        })
        return key

    def sell_leg(self, contract: dict, credit: float):
        """Sell one leg (receive credit as margin)"""
        key = f"{contract['symbol']}_SELL"
        self.positions[key] = {
            'action': 'SELL', 'contract': contract, 'premium': credit,
            'credit': credit, 'qty': 1, 'entry_time': datetime.now(timezone.utc).isoformat(),
            'status': 'open', 'margin_used': credit * 0.1  # margin is fraction of notional
        }
        self.cash += credit - (credit * 0.1)  # keep 10% as margin reserve
        self.trades.append({
            'ts': datetime.now(timezone.utc).isoformat(), 'action': 'SELL',
            'symbol': contract['symbol'], 'strike': contract['strike'],
            'type': contract['type'], 'credit': credit, 'spot': contract.get('spot')
        })
        return key

    def close_leg(self, key: str, bid: float, spot: float):
        """Close a position at current bid"""
        if key not in self.positions:
            return 0
        pos = self.positions[key]
        pnl = 0
        if pos['action'] == 'BUY':
            # Sell back at bid
            pnl = bid - pos['premium']
            self.cash += bid
        else:
            # Buy back to close (pay ask)
            pnl = pos['premium'] - bid
            self.cash -= bid
        pos['status'] = 'closed'
        pos['close_pnl'] = pnl
        pos['close_time'] = datetime.now(timezone.utc).isoformat()
        pos['close_spot'] = spot
        return round(pnl, 2)

    def total_pnl(self):
        closed = [p for p in self.positions.values() if p.get('close_pnl') is not None]
        return sum(p['close_pnl'] for p in closed), len(closed)


class OptionsStrategyTester:
    """Tests options strategies on the paper account"""

    def __init__(self, equity: float = 50000):
        self.account = PaperOptionsAccount(equity)
        self.market = GevOptionsMarket()

    def run_credit_put_spread(self, spot: float, exp_days: int = 30):
        """Sell put spread: collect credit when IV is high"""
        self.market.set_spot(spot)
        chain = self.market.get_full_chain([exp_days])
        exp_contracts = chain['chains'][exp_days]
        
        # Find ATM and 10% OTM puts
        atm_put = None
        otm_put = None
        for c in exp_contracts:
            if c['type'] == 'put':
                if abs(c['strike'] - spot) < 0.5:
                    atm_put = c
                elif c['strike'] < spot * 0.9:
                    otm_put = c
        
        if not atm_put or not otm_put:
            return {'error': 'No valid put spread found'}

        # Sell atm put, buy otm put for protection
        short_credit = atm_put['ask']
        long_cost = otm_put['bid']
        net_credit = short_credit - long_cost
        
        ok, msg = self.account.check_risk(0, (atm_put['strike'] - otm_put['strike']))
        if not ok:
            return {'error': msg}

        short_key = self.account.sell_leg(atm_put, short_credit)
        long_key = self.account.buy_leg(otm_put, long_cost, long_cost)

        return {
            'strategy': 'Credit Put Spread',
            'short_strike': atm_put['strike'],
            'long_strike': otm_put['strike'],
            'net_credit': round(net_credit, 2),
            'max_profit': round(net_credit, 2),
            'max_loss': round(atm_put['strike'] - otm_put['strike'] - net_credit, 2),
            'spot': spot,
            'entries': [short_key, long_key]
        }

    def run_iron_condor(self, spot: float, exp_days: int = 30):
        """Iron condor: sell both sides when IV high"""
        self.market.set_spot(spot)
        chain = self.market.get_full_chain([exp_days])
        exp_contracts = chain['chains'][exp_days]

        puts = sorted([c for c in exp_contracts if c['type'] == 'put'], key=lambda x: x['strike'])
        calls = sorted([c for c in exp_contracts if c['type'] == 'call'], key=lambda x: x['strike'])

        if len(puts) < 2 or len(calls) < 2:
            return {'error': 'Not enough contracts'}

        # Sell put spread
        short_put = puts[2]  # ATM-ish
        long_put = puts[3]   # 10-15% OTM
        put_credit = short_put['ask'] - long_put['bid']

        # Sell call spread
        short_call = calls[2]  # ATM-ish
        long_call = calls[3]   # 10-15% OTM
        call_credit = short_call['ask'] - long_call['bid']

        total_credit = put_credit + call_credit
        width = max(short_put['strike'] - long_put['strike'],
                    short_call['strike'] - long_call['strike'])

        ok, msg = self.account.check_risk(0, width - total_credit)
        if not ok:
            return {'error': msg}

        keys = []
        for leg in [short_put, long_put, short_call, long_call]:
            if leg['type'] == 'put':
                if leg['strike'] == short_put['strike']:
                    k = self.account.sell_leg(leg, leg['ask'])
                else:
                    k = self.account.buy_leg(leg, leg['bid'], leg['bid'])
            else:
                if leg['strike'] == short_call['strike']:
                    k = self.account.sell_leg(leg, leg['ask'])
                else:
                    k = self.account.buy_leg(leg, leg['bid'], leg['bid'])
            keys.append(k)

        return {
            'strategy': 'Iron Condor',
            'put_short': short_put['strike'],
            'put_long': long_put['strike'],
            'call_short': short_call['strike'],
            'call_long': long_call['strike'],
            'total_credit': round(total_credit, 2),
            'width': width,
            'max_profit': round(total_credit, 2),
            'max_loss': round(width - total_credit, 2),
            'entries': keys
        }

    def simulate_expiry(self, spot: float):
        """Close all positions at expiry based on spot"""
        self.market.set_spot(spot)
        closed_pnl = 0
        
        for key in list(self.account.positions.keys()):
            if self.account.positions[key]['status'] != 'open':
                continue
            pos = self.account.positions[key]
            contract = pos['contract']
            strike = contract['strike']
            opt_type = contract['type']
            
            # Calculate intrinsic value at expiry
            if opt_type == 'call':
                intrinsic = max(0, spot - strike)
            else:
                intrinsic = max(0, strike - spot)
            
            if intrinsic > 0.01:
                # Assign/will be exercised — buy back at intrinsic
                pnl = self.account.close_leg(key, 0, spot)  # 0 bid at expiry for ITM
                if pos['action'] == 'BUY':
                    pnl -= intrinsic  # Loss = premium paid - intrinsic value lost
                else:
                    pnl -= intrinsic  # Loss = credit received - intrinsic value owed
                pos['close_pnl'] = pnl
            else:
                # Expires worthless
                if pos['action'] == 'BUY':
                    pnl = -pos['premium']  # Lose premium
                    self.account.close_leg(key, 0, spot)
                else:
                    pnl = pos['premium']  # Keep credit
                    self.account.close_leg(key, 0, spot)
            closed_pnl += pnl

        return round(closed_pnl, 2)


def demo():
    """Run strategy tests"""
    tester = OptionsStrategyTester(50000)
    
    spot = 10.00
    print(f"=== GEV Options Paper Testing — Spot: ${spot} ===\n")

    # Test credit put spread
    result = tester.run_credit_put_spread(spot, 30)
    print("1. Credit Put Spread:")
    print(f"   Net credit: ${result.get('net_credit', 0):.2f}")
    print(f"   Max profit: ${result.get('max_profit', 0):.2f}")
    print(f"   Max loss: ${result.get('max_loss', 0):.2f}")
    
    # Simulate expiry at different levels
    for target_spot in [10.0, 9.0, 8.0, 11.0]:
        pnl = tester.simulate_expiry(target_spot)
        print(f"   Spot at expiry ${target_spot}: P&L ${pnl:.2f}")

    # Test iron condor
    tester2 = OptionsStrategyTester(50000)
    result2 = tester2.run_iron_condor(spot, 30)
    print(f"\n2. Iron Condor:")
    print(f"   Total credit: ${result2.get('total_credit', 0):.2f}")
    print(f"   Max profit: ${result2.get('max_profit', 0):.2f}")
    print(f"   Max loss: ${result2.get('max_loss', 0):.2f}")
    
    for target_spot in [10.0, 9.0, 8.0, 11.0, 12.0]:
        pnl = tester2.simulate_expiry(target_spot)
        print(f"   Spot at expiry ${target_spot}: P&L ${pnl:.2f}")


if __name__ == "__main__":
    demo()
