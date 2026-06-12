"""APScheduler-based daily scheduler.

Runs `main.run_pipeline` once a day at `config.yaml` `schedule.daily_time`
(24-hour, local timezone). For deployments that already have cron available
(e.g. a server or container with a crontab), prefer cron + `python main.py
--run-now` over running this process persistently — this scheduler exists
for environments where a long-running process is more convenient than
configuring cron.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from config import load_config
from main import run_pipeline

logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    config = load_config()
    daily_time = config.get("schedule", {}).get("daily_time", "07:00")
    hour, minute = (int(part) for part in daily_time.split(":"))

    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=hour, minute=minute)

    logger.info("Scheduler started; pipeline will run daily at %02d:%02d", hour, minute)
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    start_scheduler()
