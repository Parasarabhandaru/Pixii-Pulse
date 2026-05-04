"""APScheduler — runs the daily Pixii Pulse pipeline at 8:00 AM and logs the briefing."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from main import run_pipeline_for_scenario
from utils.notifier import send_morning_briefing


def daily_oracle_run() -> None:
    """Run the default Pixii scenario and log the prepared 3 actions."""
    print("Pixii Pulse Scheduler: Running daily analysis...")
    try:
        result = run_pipeline_for_scenario("yoga_mat")
        cards = result["cards"]
        send_morning_briefing(cards)
        print("Pixii Pulse Scheduler: Complete. Actions prepared.")
    except Exception as exc:
        print(f"Pixii Pulse Scheduler: Failed — {exc}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_oracle_run, "cron", hour=8, minute=0, id="pixii_pulse_daily")
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    daily_oracle_run()
