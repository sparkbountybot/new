
#!/usr/bin/env python3

import os

os.chdir('/tmp/bounty-bot')
files = {
      '.gitignore': 'pycache/\n.pyc\n.venv/\n/tmp/bountybot_.json\n',
      'requirements.txt':
  'alpaca-py==0.30.0\napscheduler==3.10.4\npyyaml==6.0.1\nsendgrid==6.11.0\nrequests==2.32.3\ngspread==6.1.2\ngoogle-api-python-client==2.138.0\ngoogle-auth-oauthlib==1.2.0\ngoogle-auth-httplib2==0.2.0\nmarkdown-it-py==3.0.0\n',    'README.md': '# BountyBot\n\n## Components\n\nmanager.py      CLI controller\nbounty_scanner.py  Scans GitHub for bounty-worthy issues\ntrader.py          Paper trading via Alpaca API\ngmail_monitor.py   Watches Gmail for GitHub notifications\nemail_utils.py     Sends reports via Gmail/SendGrid\n\n## Commands\n\nmanager.py status   Show state\nmanager.py scan     One-time scan\nmanager.py query    Show alerts\nmanager.py trade-status  Show trading\nmanager.py trade-scan  Execute trades\nmanager.py send-test  Test Gmail\n',    'config.yaml': '# Configuration\n\ngithub:\n  org: sparkbountybot\n  watch_interval_seconds: 300\n\ngmail:\n  email: your@gmail.com\n  password: your-app-password\n  check_interval_seconds: 300\n\ntrading:\n  alpaca_api_key: your-api-key\n  alpaca_secret_key: your-secret-key\n  base_url: https://paper-api.alpaca.markets\n  paper: true\n  max_position_pct: 0.3\n  max_total_risk: 0.05\n\nemail:\n  from: bountybot@sparkbountybot.com\n\nsendgrid:\n  api_key: your-sendgrid-key\n',                              }
for name, content in files.items():
    with open(name, 'w') as f:
        f.write(content)
print('Created:', sorted(files.keys()))
print('All files:', sorted(os.listdir('.')))
