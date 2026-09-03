#!/usr/bin/env python3
"""
Options Greeks Calculator — Black-Scholes Model
No external data needed — feeds in S, K, T, r, sigma to get price + greeks
Ready to plug into engine once we get data access
"""
import math
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class OptionResult:
    """Black-Scholes pricing and greeks"""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class GreeksCalculator:
    """Black-Scholes option pricing and greeks calculator"""
    
    @staticmethod
    def norm_cdf(x: float) -> float:
        """Standard normal cumulative distribution function"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    @staticmethod
    def norm_pdf(x: float) -> float:
        """Standard normal probability density function"""
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
    
    @classmethod
    def calculate(
        cls,
        spot: float,      # S — current stock price
        strike: float,    # K — option strike price
        years: float,     # T — time to expiration (in years)
        rate: float,      # r — risk-free rate (decimal, e.g., 0.05 for 5%)
        volatility: float,  # sigma — implied volatility (decimal, e.g., 1.0 for 100%)
        option_type: Literal['call', 'put'] = 'call'
    ) -> OptionResult:
        """
        Calculate option price and all greeks using Black-Scholes.
        
        Args:
            spot: Current stock price
            strike: Option strike price
            years: Time to expiration in years (30 days = 30/365)
            rate: Risk-free interest rate (decimal)
            volatility: Implied volatility (decimal)
            option_type: 'call' or 'put'
        
        Returns:
            OptionResult with price, delta, gamma, theta, vega, rho
        """
        if years <= 0:
            # At expiration
            if option_type == 'call':
                intrinsic = max(spot - strike, 0)
            else:
                intrinsic = max(strike - spot, 0)
            return OptionResult(
                price=intrinsic,
                delta=1.0 if spot > strike else (-1.0 if spot < strike else 0.0),
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0
            )
        
        if volatility <= 0:
            raise ValueError("Volatility must be > 0")
        
        # Black-Scholes d1, d2
        sqrt_t = math.sqrt(years)
        d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * years) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        
        if option_type == 'call':
            price = spot * cls.norm_cdf(d1) - strike * math.exp(-rate * years) * cls.norm_cdf(d2)
            delta = cls.norm_cdf(d1)
            theta = (
                -(spot * cls.norm_pdf(d1) * volatility) / (2 * sqrt_t)
                - rate * strike * math.exp(-rate * years) * cls.norm_cdf(d2)
            )
            rho = strike * years * math.exp(-rate * years) * cls.norm_cdf(d2)
        else:  # put
            price = strike * math.exp(-rate * years) * cls.norm_cdf(-d2) - spot * cls.norm_cdf(-d1)
            delta = cls.norm_cdf(d1) - 1
            theta = (
                -(spot * cls.norm_pdf(d1) * volatility) / (2 * sqrt_t)
                + rate * strike * math.exp(-rate * years) * cls.norm_cdf(-d2)
            )
            rho = -strike * years * math.exp(-rate * years) * cls.norm_cdf(-d2)
        
        # Common greeks
        gamma = cls.norm_pdf(d1) / (spot * volatility * sqrt_t)
        vega = spot * cls.norm_pdf(d1) * sqrt_t
        
        return OptionResult(
            price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
    
    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        spot: float,
        strike: float,
        years: float,
        rate: float,
        option_type: Literal['call', 'put'] = 'call',
        tolerance: float = 0.0001,
        max_iter: int = 100
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            market_price: Observed market price of the option
            spot: Current stock price
            strike: Option strike price
            years: Time to expiration (in years)
            rate: Risk-free rate
            option_type: 'call' or 'put'
            tolerance: Convergence tolerance
            max_iter: Maximum iterations
        
        Returns:
            Implied volatility (decimal), or -1 if not found
        """
        vol = 0.5  # Start with 50% IV guess
        for _ in range(max_iter):
            result = cls.calculate(spot, strike, years, rate, vol, option_type)
            price_diff = result.price - market_price
            vega = result.vega
            
            if abs(vega) < 1e-10:
                break
            
            new_vol = vol - price_diff / vega
            new_vol = max(new_vol, 0.01)  # Floor at 1%
            
            if abs(new_vol - vol) < tolerance:
                vol = new_vol
                break
            vol = new_vol
        
        return vol
    
    @classmethod
    def breakeven(cls, spot: float, strike: float, price: float, option_type: str) -> float:
        """Calculate break-even price"""
        if option_type == 'call':
            return strike + price
        else:  # put
            return strike - price
    
    @classmethod
    def delta_neutral_shares(cls, option_result: OptionResult, shares: int = 100) -> int:
        """Calculate shares needed to delta-hedge"""
        delta_exposure = option_result.delta * shares
        return round(-delta_exposure)


def demo():
    """Example usage with GEV-like parameters"""
    print("=== GEV OPTIONS GREEKS CALCULATOR ===\n")
    
    # Example: GEV at $10, 30-day call, 80% IV
    S = 10.00  # Stock price
    K = 12.00  # Strike (20% OTM call)
    T = 30 / 365  # 30 days to expiration
    r = 0.05   # 5% risk-free rate
    sigma = 0.80  # 80% implied volatility
    
    print(f"Stock: ${S} | Strike: ${K} | DTE: {int(T*365)}d | IV: {sigma*100:.0f}%\n")
    
    # Call option
    call = GreeksCalculator.calculate(S, K, T, r, sigma, 'call')
    print(f"CALL ${K}:")
    print(f"  Price:  ${call.price:.2f}")
    print(f"  Delta:  {call.delta:.3f}  ({call.delta*100:.0f}%)")
    print(f"  Gamma:  {call.gamma:.4f}")
    print(f"  Theta:  ${call.theta:.3f}/day")
    print(f"  Vega:   ${call.vega:.3f} per 1% vol")
    print(f"  Breakeven: ${GreeksCalculator.breakeven(S, K, call.price, 'call'):.2f}")
    
    # Put option at same strike
    put = GreeksCalculator.calculate(S, K, T, r, sigma, 'put')
    print(f"\nPUT ${K}:")
    print(f"  Price:  ${put.price:.2f}")
    print(f"  Delta:  {put.delta:.3f}  ({put.delta*100:.0f}%)")
    print(f"  Gamma:  {put.gamma:.4f}")
    print(f"  Theta:  ${put.theta:.3f}/day")
    print(f"  Vega:   ${put.vega:.3f} per 1% vol")
    print(f"  Breakeven: ${GreeksCalculator.breakeven(S, K, put.price, 'put'):.2f}")
    
    # Spread example: Bull call spread
    K2 = 14.00  # Higher strike
    call2 = GreeksCalculator.calculate(S, K2, T, r, sigma, 'call')
    spread_price = call.price - call2.price
    spread_width = K2 - K
    spread_max = spread_width - spread_price
    spread_return = (spread_max / spread_price * 100) if spread_price > 0 else 0
    
    print(f"\nBULL CALL SPREAD (${K}/${K2}):")
    print(f"  Net debit: ${spread_price:.2f}")
    print(f"  Max loss: ${spread_price:.2f}")
    print(f"  Max gain: ${spread_max:.2f} ({spread_return:.0f}% return)")
    print(f"  Breakeven: ${GreeksCalculator.breakeven(S, K, spread_price, 'call'):.2f}")
    
    # IV calculation example
    print(f"\nIMPLIED VOLATILITY:")
    market_price = 1.50  # Say this call trades at $1.50
    iv = GreeksCalculator.implied_volatility(market_price, S, K, T, r, 'call')
    print(f"  If ${K} call trades at ${market_price}, IV = {iv*100:.1f}%")
    
    # Sensitivity: How theta changes with DTE
    print(f"\nTHETA SENSITIVITY (30-day $12 call):")
    for dte_pct in [0.5, 1.0, 2.0]:  # 0.5x, 1x, 2x time
        t2 = T * dte_pct
        c2 = GreeksCalculator.calculate(S, K, t2, r, sigma, 'call')
        print(f"  DTE={int(t2*365)}d: theta=${c2.theta:.3f}/day, price=${c2.price:.2f}")


if __name__ == "__main__":
    demo()
