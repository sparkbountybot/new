"""BountyBot Framework v2 — Automated Technical Trading & GitHub Bounty Hunting."""
from .bounty_scanner import GitHubBountyHunter
from .trader import TechnicalTrader
from .gmail_monitor import GmailMonitor
from .mail_sender import EmailSender
from .scheduler import BountyScheduler
from .dashboard import simple_dashboard
