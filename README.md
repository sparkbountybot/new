# BountyBot

## Components

manager.py      CLI controller
bounty_scanner.py  Scans GitHub for bounty-worthy issues
trader.py          Paper trading via Alpaca API
gmail_monitor.py   Watches Gmail for GitHub notifications
email_utils.py     Sends reports via Gmail/SendGrid

## Commands

manager.py status   Show state
manager.py scan     One-time scan
manager.py query    Show alerts
manager.py trade-status  Show trading
manager.py trade-scan  Execute trades
manager.py send-test  Test Gmail
