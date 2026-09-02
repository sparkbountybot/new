#!/usr/bin/env python3
"""
Autonomous Trading Engine
=========================
Runs directly on the host machine with full Alpaca API access via curl subprocess.
No Python dependencies beyond stdlib — all HTTP via curl subprocess calls.

Scans: AAPL, MSFT, NVDA, TSLA, AMZN, META, GOOGL, JPM, V, JNJ
Indicators: RSI, MACD, Bollinger Bands, Trend Strength
Generates BUY/SELL signals from composite scoring
Max 8 open positions, max 15% equity per position

SCHEDULE: Cron every 5 minutes during market hours (9:30-15:55 ET)
    */5 9-16 * * 1-5 /home/machine_learning/.trading_engine.py --run
"""

import subprocess
import json
import os
import sys
import time
import logging
import argparse
import math
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path("/home/machine_learning")
LOG_FILE = BASE_DIR / ".trading_log.txt"
STATE_FILE = BASE_DIR / ".trading_state.json"

# API Keys
# To use LIVE account, set these env vars or edit defaults below:
#   ALPACA_API_KEY=AKESB677ODE3GUAVWU24W4647X
#   ALPACA_SECRET_KEY=8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ
API_KEY = os.environ.get("ALPACA_API_KEY", "PK7I7UNRDEGHYSOWQMUCT6TM2Z")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "H5hHsrTiHgXg8gaid3QPN1Y9vuwSM8N1RkkeCVLgParh")

# Detect live vs paper by API key length (live keys differ)
PAPER_MODE = API_KEY == "PK7I7UNRDEGHYSOWQMUCT6TM2Z"

ALPACA_BASE = "https://paper.tradingalpaca.com" if PAPER_MODE else "https://api.alpaca.markets"
ACCOUNT_URL = f"{ALPACA_BASE}/v2/account"
POS_URL = f"{ALPACA_BASE}/v2/positions"
ORDERS_URL = f"{ALPACA_BASE}/v2/orders"
BARS_URL = f"{ALPACA_BASE}/v2/stocks/{{symbol}}/bars"
QUOTES_URL = f"{ALPACA_BASE}/v2/stocks/{{symbol}}/quotes/latest"
WATCHLIST_URL = f"{ALPACA_BASE}/v2/quotes"

# Scan universe
WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
    "META", "GOOGL", "JPM", "V", "JNJ",
]

# Strategy parameters
MAX_POSITIONS = 8
MAX_EQUITY_PER_POSITION = 0.15  # 15%
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_SIGNAL_THRESHOLD = 0.0005
BB_WIDTH_THRESHOLD = 0.02
TREND_LOOKBACK = 20

# Composite scoring weights
WEIGHT_RSI = 0.25
WEIGHT_MACD = 0.30
WEIGHT_BB = 0.25
WEIGHT_TREND = 0.20

# Signal thresholds
BUY_SCORE_THRESHOLD = 0.6
SELL_SCORE_THRESHOLD = -0.4

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    logger = logging.getLogger("trading_engine")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(LOG_FILE), mode="a")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s"
        ))
        logger.addHandler(ch)
    return logger


logger = setup_logging()


# ---------------------------------------------------------------------------
# Curl-based Alpaca API Client
# ---------------------------------------------------------------------------

class AlpacaClient:
    """Alpaca API client using subprocess curl calls — works in zero-network sandboxes."""

    HEADERS = [
        "APCA-API-KEY-ID: {api_key}",
        "APCA-API-SECRET-KEY: {secret_key}",
        "Content-Type: application/json",
    ]

    def __init__(self, api_key: str = API_KEY, secret_key: str = SECRET_KEY,
                 base_url: str = ALPACA_BASE):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        # Template headers
        self._headers = [h.format(api_key=api_key, secret_key=secret_key)
                         for h in self.HEADERS]

    def _build_curl(self, method: str, path: str,
                    data: Optional[Dict] = None,
                    params: Optional[Dict] = None) -> List[str]:
        """Build the curl command list."""
        cmd = ["curl", "-s", "-S", "-X", method, f"{self.base_url}{path}"]
        for h in self._headers:
            cmd.extend(["-H", h])
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = cmd[-1] if "?" not in cmd[-1] else cmd[-1].rsplit("?", 1)[0]
            cmd[-1] = f"{url}?{qs}"
        if data is not None:
            cmd.extend(["-d", json.dumps(data)])
        return cmd

    def _exec(self, method: str, path: str,
              data: Optional[Dict] = None,
              params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a curl command and return parsed JSON."""
        cmd = self._build_curl(method, path, data=data, params=params)
        logger.debug(f"curl {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                err = result.stderr or result.stdout
                raise RuntimeError(f"curl failed ({result.returncode}): {err}")
            out = result.stdout.strip()
            if not out:
                return {}
            return json.loads(out)
        except subprocess.TimeoutExpired:
            raise RuntimeError("curl timed out after 30s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON parse error: {e}. Output: {result.stdout[:200]}")

    def get_account(self) -> Dict[str, Any]:
        """Fetch account info — buying power, equity, status."""
        return self._exec("GET", "/v2/account")

    def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch all open positions."""
        data = self._exec("GET", "/v2/positions")
        return data if isinstance(data, list) else []

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific position."""
        try:
            return self._exec("GET", f"/v2/positions/{symbol}")
        except RuntimeError:
            return None

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetch an order by ID."""
        try:
            return self._exec("GET", f"/v2/orders/{order_id}")
        except RuntimeError:
            return None

    def get_orders(self, status: str = "open",
                   limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch orders with optional status filter."""
        return self._exec("GET", "/v2/orders", params={
            "status": status, "limit": str(limit), "direction": "asc"
        })

    def submit_order(self, symbol: str, qty: int, side: str,
                     type: str = "market", time_in_force: str = "day",
                     limit_price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> Dict[str, Any]:
        """Submit a market/limit order."""
        data: Dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": type,
            "time_in_force": time_in_force,
        }
        if limit_price:
            data["limit_price"] = str(limit_price)
        if stop_price:
            data["stop_price"] = str(stop_price)
        return self._exec("POST", "/v2/orders", data=data)

    def cancel_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Cancel all open orders, optionally filtered by symbol."""
        data = self._exec("GET", "/v2/orders", params={
            "status": "open", "limit": "100"
        })
        canceled = []
        if isinstance(data, list):
            for order in data:
                if symbol and order.get("symbol") != symbol:
                    continue
                oid = order.get("id")
                if oid:
                    try:
                        self._exec("DELETE", f"/v2/orders/{oid}")
                        canceled.append(oid)
                    except RuntimeError:
                        pass
        return canceled

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a single order by ID."""
        try:
            self._exec("DELETE", f"/v2/orders/{order_id}")
            return True
        except RuntimeError:
            return False

    def get_bars(self, symbol: str,
                 timeframe: str = "5Min",
                 limit: int = 100,
                 start: Optional[str] = None,
                 end: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch OHLCV bars for a symbol."""
        params: Dict[str, str] = {
            "timeframe": timeframe,
            "limit": str(limit),
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._exec("GET",
                          f"/v2/stocks/{symbol}/bars", params=params)

    def get_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest bid/ask quotes for a symbol."""
        try:
            return self._exec("GET", f"/v2/stocks/{symbol}/quotes/latest")
        except RuntimeError:
            return None

    def get_last_trade(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch the last trade for a symbol."""
        try:
            data = self._exec("GET", f"/v2/stocks/{symbol}/trades/latest")
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data:
                return data[0]
            return None
        except RuntimeError:
            return None


# ---------------------------------------------------------------------------
# Technical Indicator Calculators
# ---------------------------------------------------------------------------

class Indicators:
    """Pure-Python technical indicator calculations from OHLCV bar data."""

    @staticmethod
    def _extract_closes(bars: List[Dict[str, Any]]) -> List[float]:
        """Extract close prices from bar dicts."""
        closes = []
        for b in bars:
            try:
                closes.append(float(b.get("c", 0)))
            except (TypeError, ValueError):
                pass
        return closes

    @staticmethod
    def _extract_highs(bars: List[Dict[str, Any]]) -> List[float]:
        closes = []
        for b in bars:
            try:
                closes.append(float(b.get("h", 0)))
            except (TypeError, ValueError):
                pass
        return closes

    @staticmethod
    def _extract_lows(bars: List[Dict[str, Any]]) -> List[float]:
        closes = []
        for b in bars:
            try:
                closes.append(float(b.get("l", 0)))
            except (TypeError, ValueError):
                pass
        return closes

    @staticmethod
    def _extract_volumes(bars: List[Dict[str, Any]]) -> List[float]:
        vols = []
        for b in bars:
            try:
                vols.append(float(b.get("v", 0)))
            except (TypeError, ValueError):
                pass
        return vols

    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI using Wilder's smoothing method.
        Returns None if not enough data."""
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        recent_gains = deltas[-period:]
        recent_losses = [abs(d) for d in recent_gains if d < 0]
        avg_gain = sum(recent_gains) / period if all(d >= 0 for d in recent_gains) else 0
        avg_loss = sum(recent_losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    def compute_rsi(self, bars: List[Dict[str, Any]],
                    period: int = 14) -> Optional[float]:
        """Compute RSI from bar data."""
        closes = self._extract_closes(bars)
        return self.rsi(closes, period)

    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Compute Exponential Moving Average."""
        if not prices or len(prices) < period:
            return []
        multiplier = 2.0 / (period + 1)
        ema_vals = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema_vals.append((price - ema_vals[-1]) * multiplier + ema_vals[-1])
        return ema_vals

    def macd(self, closes: List[float],
             fast: int = 12, slow: int = 26,
             signal: int = 9) -> Optional[Dict[str, float]]:
        """Calculate MACD line, signal line, and histogram."""
        if len(closes) < slow + signal:
            return None
        fast_ema = self.ema(closes, fast)
        slow_ema = self.ema(closes, slow)
        # Align — slow_ema is shorter by (slow - fast)
        offset = len(fast_ema) - len(slow_ema)
        macd_line = [fast_ema[i + offset] - slow_ema[i]
                     for i in range(len(slow_ema))]
        if len(macd_line) < signal:
            return None
        signal_line = self.ema(macd_line, signal)
        if not signal_line:
            return None
        histogram = [macd_line[-1] - signal_line[-1]]
        return {
            "macd": round(macd_line[-1], 6),
            "signal": round(signal_line[-1], 6),
            "histogram": round(histogram[0], 6),
        }

    def compute_macd(self, bars: List[Dict[str, Any]],
                     fast: int = 12, slow: int = 26,
                     signal: int = 9) -> Optional[Dict[str, float]]:
        """Compute MACD from bar data."""
        closes = self._extract_closes(bars)
        return self.macd(closes, fast, slow, signal)

    @staticmethod
    def bollinger_bands(closes: List[float],
                        period: int = 20,
                        num_std: float = 2.0) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands."""
        if len(closes) < period:
            return None
        window = closes[-period:]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = math.sqrt(variance)
        upper = sma + num_std * std
        lower = sma - num_std * std
        last_price = closes[-1]
        # %B: where price sits within the bands [0, 1]
        bandwidth = (upper - lower) / sma if sma != 0 else 0
        pct_b = (last_price - lower) / (upper - lower) if (upper - lower) != 0 else 0.5
        return {
            "sma": round(sma, 4),
            "upper": round(upper, 4),
            "lower": round(lower, 4),
            "bandwidth": round(bandwidth, 6),
            "pct_b": round(pct_b, 4),
            "current_price": round(last_price, 4),
        }

    def compute_bollinger(self, bars: List[Dict[str, Any]],
                          period: int = 20,
                          num_std: float = 2.0) -> Optional[Dict[str, float]]:
        """Compute Bollinger Bands from bar data."""
        closes = self._extract_closes(bars)
        return self.bollinger_bands(closes, period, num_std)

    @staticmethod
    def trend_strength(closes: List[float], period: int = 20) -> Optional[float]:
        """Calculate trend strength as normalized slope via linear regression.
        Returns value in [-1, 1]. Positive = uptrend, negative = downtrend."""
        if len(closes) < 2:
            return None
        n = len(closes)
        x_mean = (n - 1) / 2.0
        y_mean = sum(closes) / n
        num = sum((i - x_mean) * (closes[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 0.0
        slope = num / den
        # Normalize: slope / average_price
        avg_price = y_mean if y_mean != 0 else 1.0
        normalized = slope / avg_price
        # Clip to [-1, 1]
        return round(max(-1.0, min(1.0, normalized * 100)), 4)

    def compute_trend(self, bars: List[Dict[str, Any]],
                      period: int = 20) -> Optional[float]:
        """Compute trend strength from bar data."""
        closes = self._extract_closes(bars)
        return self.trend_strength(closes, period)


# ---------------------------------------------------------------------------
# Signal Generation & Composite Scoring
# ---------------------------------------------------------------------------

class Signal:
    """Represents a trading signal generated by the scoring engine."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"

    def __init__(self, symbol: str, action: str, score: float,
                 details: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.action = action
        self.score = round(score, 4)
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "score": self.score,
            "details": self.details,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"Signal({self.symbol} {self.action} score={self.score:.4f})"


class SignalGenerator:
    """Generates BUY/SELL/HOLD signals from technical indicators."""

    def score_rsi(self, rsi_val: Optional[float]) -> float:
        """Score RSI component. Range: [-1, 1].
        Oversold = bullish (+1), overbought = bearish (-1)."""
        if rsi_val is None:
            return 0.0
        if rsi_val <= RSI_OVERSOLD:
            return 1.0  # Strong buy signal — oversold
        if rsi_val <= RSI_OVERSOLD + 10:
            return 0.5 + 0.5 * ((rsi_val - RSI_OVERSOLD) / 10)
        if rsi_val >= RSI_OVERBOUGHT:
            return -1.0  # Strong sell signal — overbought
        if rsi_val >= RSI_OVERBOUGHT - 10:
            return -0.5 - 0.5 * ((RSI_OVERBOUGHT - rsi_val) / 10)
        # Neutral zone — slight momentum tilt
        mid = (RSI_OVERSOLD + RSI_OVERBOUGHT) / 2
        if rsi_val < mid:
            return -0.3 * ((mid - rsi_val) / (mid - RSI_OVERSOLD))
        return 0.3 * ((rsi_val - mid) / (RSI_OVERBOUGHT - mid))

    def score_macd(self, macd_data: Optional[Dict[str, float]]) -> float:
        """Score MACD component. Range: [-1, 1].
        Bullish crossover = positive, bearish = negative."""
        if not macd_data:
            return 0.0
        hist = macd_data.get("histogram", 0)
        macd_val = macd_data.get("macd", 0)
        sig_val = macd_data.get("signal", 0)
        # Histogram direction and magnitude
        if abs(macd_val) < 1e-10:
            return 0.0
        norm_hist = hist / abs(macd_val)
        norm_hist = max(-1.0, min(1.0, norm_hist))
        # Crossover confirmation
        if macd_val > sig_val and hist > 0:
            return 0.5 + 0.5 * norm_hist  # Bullish
        elif macd_val < sig_val and hist < 0:
            return -0.5 - 0.5 * abs(norm_hist)  # Bearish
        return norm_hist * 0.3

    def score_bollinger(self, bb: Optional[Dict[str, float]]) -> float:
        """Score Bollinger Bands component. Range: [-1, 1].
        Price near lower band = bullish, near upper = bearish."""
        if not bb:
            return 0.0
        pct_b = bb.get("pct_b", 0.5)
        bw = bb.get("bandwidth", 0)
        # Squeeze detection — low bandwidth + low pct_b = potential big move up
        if bw < BB_WIDTH_THRESHOLD:
            if pct_b < 0.3:
                return 0.7  # Squeeze + bottom = buy
            elif pct_b > 0.7:
                return -0.7  # Squeeze + top = sell
            return 0.2  # Neutral during squeeze
        # Normal bands
        if pct_b < 0.2:
            return 0.6 + 0.4 * (1 - pct_b / 0.2)  # Near lower
        elif pct_b > 0.8:
            return -0.6 - 0.4 * ((pct_b - 0.8) / 0.2)  # Near upper
        # Near middle — slight momentum
        return (pct_b - 0.5) * 0.6

    def score_trend(self, trend: Optional[float]) -> float:
        """Score trend component. Range: [-1, 1].
        Trend already returns value in [-1, 1]."""
        if trend is None:
            return 0.0
        return max(-1.0, min(1.0, trend))

    def generate_signal(self, symbol: str,
                        rsi_val: Optional[float],
                        macd_data: Optional[Dict[str, float]],
                        bb: Optional[Dict[str, float]],
                        trend: Optional[float]) -> Signal:
        """Generate composite BUY/SELL/HOLD signal."""
        s_rsi = self.score_rsi(rsi_val)
        s_macd = self.score_macd(macd_data)
        s_bb = self.score_bollinger(bb)
        s_trend = self.score_trend(trend)

        composite = (
            WEIGHT_RSI * s_rsi +
            WEIGHT_MACD * s_macd +
            WEIGHT_BB * s_bb +
            WEIGHT_TREND * s_trend
        )

        # Determine action
        if composite >= BUY_SCORE_THRESHOLD:
            action = Signal.BUY
        elif composite <= SELL_SCORE_THRESHOLD:
            action = Signal.SELL
        else:
            action = Signal.HOLD

        signal = Signal(symbol, action, composite, {
            "rsi": rsi_val,
            "rsi_score": round(s_rsi, 4),
            "macd": macd_data,
            "macd_score": round(s_macd, 4),
            "bollinger": bb,
            "bb_score": round(s_bb, 4),
            "trend": trend,
            "trend_score": round(s_trend, 4),
            "composite": round(composite, 4),
        })
        return signal


# ---------------------------------------------------------------------------
# State Persistence
# ---------------------------------------------------------------------------

class StateManager:
    """Load and save trading state to JSON file."""

    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.state: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """Load state from disk. Returns empty dict if file missing."""
        try:
            if self.path.exists():
                with open(self.path, "r") as f:
                    self.state = json.load(f)
                logger.debug(f"Loaded state from {self.path}")
            else:
                self.state = {}
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state: {e}. Starting fresh.")
            self.state = {}
        # Ensure required keys
        self.state.setdefault("run_count", 0)
        self.state.setdefault("total_trades", 0)
        self.state.setdefault("winning_trades", 0)
        self.state.setdefault("last_run", None)
        self.state.setdefault("signals_history", [])
        return self.state

    def save(self) -> None:
        """Persist state to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
            logger.debug(f"Saved state to {self.path}")
        except IOError as e:
            logger.error(f"Failed to save state: {e}")

    def add_signal_history(self, signal: Signal, max_history: int = 100) -> None:
        """Append a signal to history, trimming to max_history."""
        self.state["signals_history"].append(signal.to_dict())
        if len(self.state["signals_history"]) > max_history:
            self.state["signals_history"] = self.state["signals_history"][-max_history:]

    def record_trade(self, symbol: str, side: str, qty: int,
                     price: float, order_id: str) -> None:
        """Record a trade for stats tracking."""
        self.state["total_trades"] = self.state.get("total_trades", 0) + 1
        logger.info(f"Trade recorded: {side} {qty}x {symbol} @ ${price}")

    def increment_run(self) -> None:
        self.state["run_count"] = self.state.get("run_count", 0) + 1
        self.state["last_run"] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Position Manager — enforces risk limits
# ---------------------------------------------------------------------------

class PositionManager:
    """Manages position sizing and risk constraints."""

    def __init__(self, equity: float, api_client: AlpacaClient,
                 state: StateManager):
        self.equity = equity
        self.api = api_client
        self.state_mgr = state

    def current_equity(self) -> float:
        """Fetch real-time account equity from Alpaca."""
        try:
            acc = self.api.get_account()
            eq = acc.get("equity")
            if eq:
                self.equity = float(eq)
                return self.equity
        except Exception as e:
            logger.warning(f"Failed to fetch equity: {e}")
        return self.equity

    def max_shares(self, symbol: str, price: float) -> int:
        """Calculate max shares allowed per position (15% equity limit)."""
        alloc = self.equity * MAX_EQUITY_PER_POSITION
        if price <= 0:
            return 0
        return max(1, int(alloc / price))

    def current_position_qty(self, symbol: str) -> int:
        """Get current position size."""
        pos = self.api.get_position(symbol)
        if pos:
            try:
                return int(float(pos.get("qty", 0)))
            except (TypeError, ValueError):
                pass
        return 0

    def can_open_new_position(self, open_positions: List[Dict]) -> bool:
        """Check if we can open a new position (max 8 constraint)."""
        active_positions = [p for p in open_positions
                           if float(p.get("avg_entry_price", 0)) > 0]
        return len(active_positions) < MAX_POSITIONS

    def get_current_position_count(self, open_positions: List[Dict]) -> int:
        """Count active positions."""
        return len([p for p in open_positions
                   if float(p.get("avg_entry_price", 0)) > 0])


# ---------------------------------------------------------------------------
# Main Trading Engine
# ---------------------------------------------------------------------------

class TradingEngine:
    """Main engine that orchestrates scanning, signal generation, and order execution."""

    def __init__(self):
        self.api = AlpacaClient()
        self.indicators = Indicators()
        self.signals = SignalGenerator()
        self.state_mgr = StateManager()
        self.state = self.state_mgr.load()
        self.equity = 0.0
        self.position_mgr: Optional[PositionManager] = None
        self.running = False

    def initialize(self) -> bool:
        """Initialize engine — verify account, load equity."""
        logger.info("=" * 60)
        logger.info("Trading Engine Starting")
        logger.info(f"Mode: {'PAPER' if PAPER_MODE else 'LIVE'}")
        logger.info(f"API Base: {ALPACA_BASE}")
        logger.info(f"Watchlist: {', '.join(WATCHLIST)}")
        logger.info("=" * 60)

        try:
            acc = self.api.get_account()
            self.equity = float(acc.get("equity", 0))
            buying_power = acc.get("buying_power", "N/A")
            status = acc.get("status", [])

            logger.info(f"Account Equity: ${self.equity:,.2f}")
            logger.info(f"Buying Power:   ${float(buying_power):,.2f}")
            logger.info(f"Account Status: {status}")

            if "INACTIVE" in status or "DEACTIVATED" in status:
                logger.error("Account is not active. Stopping engine.")
                return False

            self.position_mgr = PositionManager(
                self.equity, self.api, self.state_mgr
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize account: {e}")
            return False

    def fetch_bars_for_symbol(self, symbol: str) -> Optional[List[Dict]]:
        """Fetch 100 5-minute bars for a symbol."""
        try:
            bars = self.api.get_bars(symbol, timeframe="5Min", limit=100)
            if bars and isinstance(bars, list) and len(bars) > 0:
                return bars
        except Exception as e:
            logger.warning(f"Failed to fetch bars for {symbol}: {e}")
        return None

    def analyze_symbol(self, symbol: str) -> Optional[Signal]:
        """Run full technical analysis on a single symbol."""
        bars = self.fetch_bars_for_symbol(symbol)
        if not bars or len(bars) < 26:  # Need minimum for MACD
            logger.debug(f"Skipping {symbol}: insufficient bar data ({len(bars) or 0} bars)")
            return None

        rsi = self.indicators.compute_rsi(bars)
        macd_data = self.indicators.compute_macd(bars)
        bb = self.indicators.compute_bollinger(bars)
        trend = self.indicators.compute_trend(bars)

        price_data = self.indicators._extract_closes(bars)
        current_price = price_data[-1] if price_data else 0

        signal = self.signals.generate_signal(
            symbol, rsi, macd_data, bb, trend
        )

        logger.info(
            f"{symbol}: RSI={rsi}, MACD_hist={macd_data.get('histogram') if macd_data else 'N/A':>8}, "
            f"BB_pctB={bb.get('pct_b') if bb else 'N/A':>6}, "
            f"Trend={trend:>8}, Score={signal.score:>6} => {signal.action}"
        )

        return signal

    def scan_universe(self) -> List[Signal]:
        """Scan all symbols in the watchlist."""
        signals = []
        logger.info(f"Scanning {len(WATCHLIST)} symbols...")
        for symbol in WATCHLIST:
            signal = self.analyze_symbol(symbol)
            if signal and signal.action != Signal.HOLD:
                signals.append(signal)
        return signals

    def execute_signal(self, signal: Signal) -> Optional[Dict]:
        """Execute a BUY or CLOSE signal as an actual order."""
        if self.position_mgr is None:
            logger.warning("Position manager not initialized. Cannot execute.")
            return None

        # Refresh equity
        self.position_mgr.current_equity()

        # Fetch current price via quotes
        try:
            quote = self.api.get_quotes(signal.symbol)
            if quote:
                bid = quote.get("bid_price")
                if bid:
                    price = float(bid)
                else:
                    price = float(quote.get("bp", 0) or 0)
            else:
                price = 0
        except Exception as e:
            logger.warning(f"Failed to fetch price for {signal.symbol}: {e}")
            price = 0

        if price <= 0:
            logger.warning(f"Invalid price for {signal.symbol}. Skipping.")
            return None

        if signal.action == Signal.BUY:
            return self._execute_buy(signal, price)
        elif signal.action == Signal.SELL:
            return self._execute_sell(signal, price)
        return None

    def _execute_buy(self, signal: Signal, price: float) -> Optional[Dict]:
        """Execute a BUY order."""
        logger.info(f"BUY signal for {signal.symbol} @ ~${price:.2f} "
                    f"(score={signal.score:.4f})")

        # Check position limits
        try:
            positions = self.api.get_positions()
        except Exception:
            positions = []

        if not self.position_mgr.can_open_new_position(positions):
            logger.warning(f"Cannot buy {signal.symbol}: max positions ({MAX_POSITIONS}) reached")
            return None

        pos_qty = self.position_mgr.current_position_qty(signal.symbol)
        if pos_qty > 0:
            logger.info(f"{signal.symbol} already has {pos_qty} shares. Skipping buy.")
            return None

        max_shares = self.position_mgr.max_shares(signal.symbol, price)
        if max_shares <= 0:
            logger.warning(f"Cannot determine share size for {signal.symbol}")
            return None

        # Round down to avoid partial fills exceeding limit
        order_qty = min(max_shares, max(1, max_shares))

        try:
            order = self.api.submit_order(
                symbol=signal.symbol,
                qty=order_qty,
                side="buy",
                type="market",
                time_in_force="day",
            )
            order_id = order.get("id", "unknown")
            logger.info(f"BUY order submitted: {signal.symbol} {order_qty} shares "
                       f"(order_id={order_id})")
            self.state_mgr.record_trade(signal.symbol, "BUY", order_qty, price, order_id)
            return order
        except Exception as e:
            logger.error(f"Failed to submit BUY order for {signal.symbol}: {e}")
            return None

    def _execute_sell(self, signal: Signal, price: float) -> Optional[Dict]:
        """Execute a SELL (close) order."""
        symbol = signal.symbol
        logger.info(f"SELL signal for {symbol} @ ~${price:.2f} "
                    f"(score={signal.score:.4f})")

        pos_qty = self.position_mgr.current_position_qty(symbol)
        if pos_qty <= 0:
            logger.info(f"No position in {symbol} to sell. Skipping.")
            return None

        logger.info(f"Selling {pos_qty} shares of {symbol}")
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=pos_qty,
                side="sell",
                type="market",
                time_in_force="day",
            )
            order_id = order.get("id", "unknown")
            logger.info(f"SELL order submitted: {symbol} {pos_qty} shares "
                       f"(order_id={order_id})")
            self.state_mgr.record_trade(symbol, "SELL", pos_qty, price, order_id)
            return order
        except Exception as e:
            logger.error(f"Failed to submit SELL order for {symbol}: {e}")
            return None

    def run_scan(self) -> int:
        """Run a full scan cycle. Returns number of orders placed."""
        logger.info("-" * 40)
        logger.info("Starting scan cycle")

        self.position_mgr.current_equity()
        signals = self.scan_universe()

        orders_placed = 0
        for sig in signals:
            order = self.execute_signal(sig)
            if order:
                orders_placed += 1
            self.state_mgr.add_signal_history(sig)

        self.state_mgr.increment_run()
        self.state_mgr.save()

        logger.info(f"Scan complete. {len(signals)} signals, {orders_placed} orders placed")
        return orders_placed

    def run_once(self) -> int:
        """Full run: initialize + scan. Returns orders placed."""
        if not self.initialize():
            logger.error("Engine initialization failed. Aborting.")
            return 0

        return self.run_scan()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Trading Engine — Alpaca API via curl"
    )
    parser.add_argument(
        "--run", action="store_true", default=True,
        help="Run a single scan cycle (default)"
    )
    parser.add_argument(
        "--cron", type=int, default=0,
        help="Run continuously, sleeping N seconds between cycles (0=off)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate signals without placing actual orders"
    )
    parser.add_argument(
        "--symbol", type=str, default=None,
        help="Analyze only a specific symbol (default: full scan)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug-level logging to console"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print current engine status and exit"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Override API key from environment"
    )
    parser.add_argument(
        "--secret-key", type=str, default=None,
        help="Override secret key from environment"
    )

    args = parser.parse_args()

    if args.verbose:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)

    if args.status:
        _show_status(args.api_key, args.secret_key)
        return

    engine = _create_engine(args.api_key, args.secret_key)

    if args.dry_run:
        logger.info("DRY RUN MODE — no real orders will be placed")
        if args.symbol:
            engine.position_mgr = PositionManager(
                engine.equity or 100000, engine.api, engine.state_mgr
            )
        _dry_run_scan(engine, args.symbol)
        return

    if args.cron > 0:
        logger.info(f"Cron mode: running every {args.cron}s")
        _run_cron(engine, args.cron)
    else:
        engine.run_once()


def _create_engine(api_key: Optional[str], secret_key: Optional[str]):
    """Create a TradingEngine instance with optional key overrides."""
    global API_KEY, SECRET_KEY, ALPACA_BASE, PAPER_MODE
    if api_key:
        API_KEY = api_key
        PAPER_MODE = (api_key == "PK7I7UNRDEGHYSOWQMUCT6TM2Z")
        ALPACA_BASE = "https://paper.tradingalpaca.com" if PAPER_MODE else "https://api.alpaca.markets"
    if secret_key:
        SECRET_KEY = secret_key
    return TradingEngine()


def _dry_run_scan(engine: TradingEngine, symbol: Optional[str]):
    """Run signals in dry-run mode (no orders)."""
    if not engine.initialize():
        return

    if symbol:
        sig = engine.analyze_symbol(symbol)
        if sig:
            print(f"\n{'='*50}")
            print(f"Dry-run signal: {sig.action} {sig.symbol} "
                  f"(score={sig.score:.4f})")
            print(f"Details: {json.dumps(sig.details, indent=2)}")
            print(f"{'='*50}")
        return

    signals = engine.scan_universe()
    if signals:
        print(f"\n{'='*50}")
        print("DRY-RUN SIGNALS:")
        print(f"{'='*50}")
        for sig in signals:
            print(f"\n  {sig.action} {sig.symbol} "
                  f"(score={sig.score:.4f})")
            print(f"  Details: {json.dumps(sig.details, indent=2)}")
    else:
        print("No buy/sell signals generated.")


def _run_cron(engine: TradingEngine, interval: int):
    """Run continuously at the given interval."""
    cycle = 0
    while True:
        cycle += 1
        logger.info(f"Cron cycle #{cycle}")
        try:
            engine.run_once()
        except Exception as e:
            logger.error(f"Cron cycle #{cycle} failed: {e}", exc_info=True)
            # Continue running — don't crash the cron process
        time.sleep(interval)


def _show_status(api_key: Optional[str], secret_key: Optional[str]):
    """Print current engine status."""
    global ALPACA_BASE, PAPER_MODE, API_KEY, SECRET_KEY
    if api_key:
        API_KEY = api_key
        PAPER_MODE = (api_key == "PK7I7UNRDEGHYSOWQMUCT6TM2Z")
        ALPACA_BASE = "https://paper.tradingalpaca.com" if PAPER_MODE else "https://api.alpaca.markets"
    if secret_key:
        SECRET_KEY = secret_key

    api = AlpacaClient()
    print(f"\nTrading Engine Status")
    print(f"{'='*40}")
    print(f"Mode:        {'PAPER' if PAPER_MODE else 'LIVE'}")
    print(f"API Base:    {ALPACA_BASE}")

    try:
        acc = api.get_account()
        print(f"Equity:      ${float(acc.get('equity', 0)):,.2f}")
        print(f"Buying Pwr:  ${float(acc.get('buying_power', 0)):,.2f}")
        print(f"SMA:         ${float(acc.get('sma', 0)):,.2f}")
        print(f"DayTradeCnt: {acc.get('day_trade_count', 0)}")
        print(f"Status:      {acc.get('status', 'unknown')}")
        print()

        positions = api.get_positions()
        if positions:
            print("Open Positions:")
            for pos in positions:
                if float(pos.get("avg_entry_price", 0)) > 0:
                    print(f"  {pos.get('symbol'):>5}: "
                          f"qty={pos.get('qty')}, "
                          f"entry=${float(pos.get('avg_entry_price', 0)):.2f}, "
                          f"mktval=${float(pos.get('market_value', 0)):,.2f}")
        else:
            print("No open positions.")

        orders = api.get_orders(status="open")
        if orders:
            print(f"\nOpen Orders ({len(orders)}):")
            for o in orders:
                print(f"  {o.get('symbol'):>5}: "
                      f"{o.get('side'):>4} "
                      f"{o.get('qty')}x "
                      f"@ ${float(o.get('limit_price', o.get('market_price', 0))):.2f}")
    except Exception as e:
        print(f"Error fetching status: {e}")

    print()
    # State file info
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                st = json.load(f)
            print(f"Run Count:   {st.get('run_count', 0)}")
            print(f"Total Trades:{st.get('total_trades', 0)}")
            print(f"Last Run:    {st.get('last_run', 'never')}")
        except Exception:
            pass


if __name__ == "__main__":
    main()

