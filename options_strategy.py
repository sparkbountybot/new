#!/usr/bin/env python3
"""
Options Strategy Engine — Analyzes tradeable setups for GEV
Requires no market data — just feeds in price + IV
Integrates with options_greeks.py for greek calculations
"""
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class OptionTrade:
    name: str
    long_strike: Optional[float]
    short_strike: Optional[float]
    long_type: str  # 'call' or 'put'
    short_type: str  # 'call' or 'put'
    expiry_days: int
    description: str
    max_profit: float
    max_loss: float
    breakeven: float
    prob_profit: float  # estimated from delta
    notes: str


@dataclass
class StrategyResult:
    symbol: str
    spot: float
    iv: float
    strategies: list


class StrategyEngine:
    """Analyzes GEV options setups and generates strategy recommendations"""
    
    RISK_FREE = 0.05  # 5% risk-free rate
    
    def __init__(self, spot: float, iv: float = 0.80, account_equity: float = 45000):
        """
        Args:
            spot: Current stock price
            iv: Implied volatility (decimal)
            account_equity: Total account value for position sizing
        """
        self.spot = spot
        self.iv = iv
        self.equity = account_equity
        self.max_risk_per_trade = account_equity * 0.10  # Max 10% equity per trade
        self.max_position_size = account_equity * 0.20  # Max 20% equity in position
    
    def get_iv_percentile(self, iv: float) -> tuple:
        """Estimate if IV is high or low for a volatile stock like GEV"""
        if iv < 0.60:  # <60%
            return "LOW", "IV is below normal for GEV — consider buying options"
        elif iv < 1.00:  # 60-100%
            return "MEDIUM", "IV is in normal range for GEV"
        else:  # >100%
            return "HIGH", "IV is above normal for GEV — consider selling options"
    
    def calculate_spread(
        self,
        long_strike: float,
        short_strike: float,
        expiry_days: int,
        option_type: str = 'call'
    ) -> dict:
        """Calculate spread metrics"""
        from options_greeks import GreeksCalculator
        
        T = expiry_days / 365.0
        
        long_leg = GreeksCalculator.calculate(self.spot, long_strike, T, self.RISK_FREE, self.iv, option_type)
        short_leg = GreeksCalculator.calculate(self.spot, short_strike, T, self.RISK_FREE, self.iv, option_type)
        
        net_debit = long_leg.price - short_leg.price
        spread_width = abs(short_strike - long_strike)
        max_loss = net_debit if net_debit > 0 else 0
        max_profit = spread_width - net_debit if net_debit > 0 else 0
        breakeven = long_strike + net_debit if option_type == 'call' else long_strike - net_debit
        
        # Probability of profit approx from delta
        prob_long = long_leg.delta if option_type == 'call' else (1 + long_leg.delta)
        
        return {
            'long_strike': long_strike,
            'short_strike': short_strike,
            'option_type': option_type,
            'expiry_days': expiry_days,
            'net_debit': net_debit,
            'spread_width': spread_width,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'breakeven': breakeven,
            'return_pct': (max_profit / max_loss * 100) if max_loss > 0 else 0,
            'delta': long_leg.delta - short_leg.delta,
            'theta': long_leg.theta - short_leg.theta,
            'vega': long_leg.vega - short_leg.vega,
            'prob_profit': min(prob_long, 1.0)
        }
    
    def generate_strategies(self) -> list:
        """Generate all viable strategy setups for current parameters"""
        spot = self.spot
        iv_pct, iv_note = self.get_iv_percentile(self.iv)
        strategies = []
        
        # ─── BULLISH STRATEGIES ─────────────────────────────────────
        
        # 1. Bull Call Spread
        if spot * 1.20 > spot:  # 20% room up
            spread = self.calculate_spread(
                spot * 1.10,  # ATM call
                spot * 1.20,  # 20% OTM call
                30
            )
            strategies.append(OptionTrade(
                name="Bull Call Spread",
                long_strike=spot * 1.10,
                short_strike=spot * 1.20,
                long_type="call",
                short_type="call",
                expiry_days=30,
                description=f"Buy {spot:.2f} call, sell {spot*1.20:.2f} call (30d)",
                max_profit=spread['max_profit'],
                max_loss=spread['max_loss'],
                breakeven=spread['breakeven'],
                prob_profit=spread['prob_profit'],
                notes=f"IV={iv_pct} | Return: {spread['return_pct']:.0f}% | Delta: {spread['delta']:.2f}"
            ))
        
        # 2. Bull Put Spread (Credit)
        if spot * 0.85 < spot:  # 15% room down
            spread = self.calculate_spread(
                spot * 0.85,  # 15% OTM put
                spot * 0.75,  # 25% OTM put
                30,
                option_type='put'
            )
            strategies.append(OptionTrade(
                name="Bull Put Spread",
                long_strike=spot * 0.85,
                short_strike=spot * 0.75,
                long_type="put",
                short_type="put",
                expiry_days=30,
                description=f"Sell {spot*0.85:.2f} put, buy {spot*0.75:.2f} put (30d)",
                max_profit=abs(spread['net_debit']),
                max_loss=spread['spread_width'] - abs(spread['net_debit']),
                breakeven=spot * 0.85,  # Simplified
                prob_profit=spread['prob_profit'],
                notes=f"IV={iv_pct} | Credit: ${abs(spread['net_debit']):.2f} | Delta: {spread['delta']:.2f}"
            ))
        
        # ─── BEARISH STRATEGIES ──────────────────────────────────────
        
        # 3. Bear Put Spread
        spread = self.calculate_spread(
            spot * 0.90,  # 10% OTM put
            spot * 0.80,  # 20% OTM put
            30,
            option_type='put'
        )
        strategies.append(OptionTrade(
            name="Bear Put Spread",
            long_strike=spot * 0.90,
            short_strike=spot * 0.80,
            long_type="put",
            short_type="put",
            expiry_days=30,
            description=f"Buy {spot*0.90:.2f} put, sell {spot*0.80:.2f} put (30d)",
            max_profit=spread['max_profit'],
            max_loss=spread['max_loss'],
            breakeven=spread['breakeven'],
            prob_profit=1 - spread['prob_profit'],
            notes=f"IV={iv_pct} | Return: {spread['return_pct']:.0f}% | Delta: {spread['delta']:.2f}"
        ))
        
        # 4. Bear Call Spread (Credit)
        spread = self.calculate_spread(
            spot * 1.20,  # 20% OTM call
            spot * 1.30,  # 30% OTM call
            30,
            option_type='call'
        )
        strategies.append(OptionTrade(
            name="Bear Call Spread",
            long_strike=spot * 1.20,
            short_strike=spot * 1.30,
            long_type="call",
            short_type="call",
            expiry_days=30,
            description=f"Sell {spot*1.20:.2f} call, buy {spot*1.30:.2f} call (30d)",
            max_profit=abs(spread['net_debit']),
            max_loss=spread['spread_width'] - abs(spread['net_debit']),
            breakeven=spot * 1.20,
            prob_profit=spread['prob_profit'],
            notes=f"IV={iv_pct} | Credit: ${abs(spread['net_debit']):.2f} | Theta: {spread['theta']:.2f}"
        ))
        
        # ─── VOLATILITY STRATEGIES ──────────────────────────────────
        
        # 5. Long Straddle (IV high → buy)
        if iv_pct == "HIGH":
            # ATM straddle
            atm_strike = round(spot)
            from options_greeks import GreeksCalculator
            T = 30 / 365.0
            call_price = GreeksCalculator.calculate(spot, atm_strike, T, self.RISK_FREE, self.iv, 'call').price
            put_price = GreeksCalculator.calculate(spot, atm_strike, T, self.RISK_FREE, self.iv, 'put').price
            straddle_cost = call_price + put_price
            
            if straddle_cost < self.max_risk_per_trade:
                strategies.append(OptionTrade(
                    name="Long Straddle",
                    long_strike=atm_strike,
                    short_strike=None,
                    long_type="both",  # both call and put
                    short_type=None,
                    expiry_days=30,
                    description=f"Buy ATM {atm_strike} call + put (30d)",
                    max_profit=float('inf'),  # Unlimited on big move
                    max_loss=straddle_cost,
                    breakeven=atm_strike,
                    prob_profit=0.40,  # Straddles need big moves
                    notes=f"IV={iv_pct} | Cost: ${straddle_cost:.2f} | Breakeven: {atm_strike * 1.04:.2f} / {atm_strike * 0.96:.2f}"
                ))
        
        # 6. Iron Condor (IV high → sell premium)
        if iv_pct == "HIGH":
            spread1 = self.calculate_spread(
                spot * 0.80, spot * 0.70, 30, 'put'
            )
            spread2 = self.calculate_spread(
                spot * 1.20, spot * 1.30, 30, 'call'
            )
            
            total_credit = abs(spread1['net_debit']) + abs(spread2['net_debit'])
            max_width = max(spread1['spread_width'], spread2['spread_width'])
            
            if total_credit > 0 and total_credit < self.max_risk_per_trade:
                strategies.append(OptionTrade(
                    name="Iron Condor",
                    long_strike=min(spread1['long_strike'], spread2['short_strike']),
                    short_strike=max(spread1['short_strike'], spread2['short_strike']),
                    long_type="both",
                    short_type="both",
                    expiry_days=30,
                    description=f"Short put spread + short call spread (30d)",
                    max_profit=total_credit,
                    max_loss=max_width - total_credit,
                    breakeven=spot,
                    prob_profit=max(spread1['prob_profit'], spread2['prob_profit']),
                    notes=f"IV={iv_pct} | Credit: ${total_credit:.2f} | Theta: positive"
                ))
        
        # ─── DIRECTIONAL (Simple) ──────────────────────────────────
        
        # 7. Long Call (if bullish + IV low)
        if iv_pct == "LOW":
            call_30dte = self.calculate_spread(spot * 1.15, spot * 1.15, 30, 'call')
            if call_30dte['net_debit'] < self.max_risk_per_trade:
                strategies.append(OptionTrade(
                    name="Long Call (15% OTM)",
                    long_strike=spot * 1.15,
                    short_strike=None,
                    long_type="call",
                    short_type=None,
                    expiry_days=30,
                    description=f"Buy 15% OTM call (30d)",
                    max_profit=float('inf'),
                    max_loss=call_30dte['net_debit'],
                    breakeven=spot * 1.15 + call_30dte['net_debit'],
                    prob_profit=0.35,
                    notes=f"IV={iv_pct} | Cheap: ${call_30dte['net_debit']:.2f}"
                ))
        
        # 8. Protective Collar (if we own shares)
        collared_breakeven = spot * 0.90  # Approximate
        strategies.append(OptionTrade(
            name="Protective Collar",
            long_strike=spot * 0.85,
            short_strike=spot * 1.15,
            long_type="put",
            short_type="call",
            expiry_days=30,
            description=f"Own shares + buy {spot*0.85:.2f} put + sell {spot*1.15:.2f} call (30d)",
            max_profit=spot * 1.15 - spot,  # Capped upside
            max_loss=spot * 0.85 - spot,  # Floor at 15%
            breakeven=collared_breakeven,
            prob_profit=0.60,
            notes=f"Downside protected to ${spot*0.85:.2f}, upside capped at ${spot*1.15:.2f}"
        ))
        
        return strategies


def demo():
    """Run the engine with GEV-like parameters"""
    print("=== GEV OPTIONS STRATEGY ENGINE ===\n")
    
    engine = StrategyEngine(spot=10.00, iv=0.80, account_equity=45000)
    strategies = engine.generate_strategies()
    
    print(f"Stock: ${engine.spot} | IV: {engine.iv*100:.0f}% | Equity: ${engine.equity:,.0f}\n")
    for i, s in enumerate(strategies, 1):
        max_p = f"${s.max_profit:,.2f}" if s.max_profit != float('inf') else "Unlimited"
        max_l = f"${s.max_loss:,.2f}" if s.max_loss != float('inf') else "Unlimited"
        prob = f"{s.prob_profit*100:.0f}%" if s.prob_profit < 1 else "N/A"
        print(f"{i}. {s.name}")
        print(f"   {s.description}")
        print(f"   Max Profit: {max_p} | Max Loss: {max_l} | BE: {s.breakeven:.2f}")
        print(f"   Prob Profit: {prob} | {s.notes}")
        print()


if __name__ == "__main__":
    demo()
