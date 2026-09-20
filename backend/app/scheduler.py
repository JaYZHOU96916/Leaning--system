import asyncio
import threading
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.alerts.service import AlertNotifier, dispatch_due_alerts, make_notifier
from app.core.config import Settings, get_settings
from app.db import get_engine


def run_ddl_alert_job(
    settings: Settings | None = None,
    notifier: AlertNotifier | None = None,
) -> int:
    settings = settings or get_settings()
    notifier = notifier or make_notifier(settings)
    with Session(get_engine(settings)) as session:
        return asyncio.run(dispatch_due_alerts(session, notifier))


def create_scheduler(
    settings: Settings | None = None,
    *,
    job: Callable[[], int] | None = None,
) -> BackgroundScheduler:
    settings = settings or get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        job or (lambda: run_ddl_alert_job(settings)),
        "interval",
        minutes=settings.ddl_alert_poll_interval_minutes,
        id="ddl-alert-check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def main() -> None:
    settings = get_settings()
    scheduler = create_scheduler(settings)
    scheduler.start()
    try:
        threading.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=True)
