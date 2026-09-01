"""
Scheduler — Manages scheduled tasks using APScheduler.
Runs bounty scanning, trading, and monitoring on cron schedules.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime


class BountyScheduler:
    """Manages scheduled tasks for BountyBot."""

    def __init__(self, main_run_func, config=None):
        self.scheduler = BlockingScheduler()
        self.config = config or {}
        self.main_run_func = main_run_func
        self.scheduling = self.config.get("scheduling", {})

    def setup(self):
        """Setup all scheduled jobs."""
        sched = self.scheduling

        # Bounty scan every 6 hours
        self.scheduler.add_job(
            self._run,
            CronTrigger.from_crontab(sched.get("job_discovery", "0 */6 * * *")),
            id="bounty_scan",
            name="Bounty Scan",
            args=["scan"],
        )

        # Trading scan every 2 hours (market hours)
        self.scheduler.add_job(
            self._run,
            CronTrigger.from_crontab(sched.get("rules_trading", "0 14,18,22,2 * * 1-5")),
            id="trading_scan",
            name="Trading Scan",
            args=["trade"],
        )

        # Health check every 2 hours
        self.scheduler.add_job(
            self._run,
            CronTrigger.from_crontab(sched.get("health_check", "0 */2 * * *")),
            id="health_check",
            name="Health Check",
            args=["status"],
        )

    def _run(self, mode="full"):
        """Run a scheduled task."""
        try:
            self.main_run_func(mode)
        except Exception as e:
            print(f"  Scheduled job error: {e}")

    def start(self):
        """Start the scheduler (blocking)."""
        print(f"\n=== Scheduler Started ===")
        print(f"  Jobs registered:")
        for job in self.scheduler.get_jobs():
            print(f"    {job.name}: {job.trigger}")
        self.scheduler.start()

    def start_daemon(self):
        """Start scheduler in daemon mode (non-blocking)."""
        from apscheduler.schedulers.background import BackgroundScheduler
        self.scheduler = BackgroundScheduler()
        self.setup()
        self.scheduler.start()
        return self.scheduler
