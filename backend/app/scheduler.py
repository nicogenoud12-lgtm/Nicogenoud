"""APScheduler bootstrap. Jobs are registered from AppSetting at startup."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from .crud import get_setting
from .database import SessionLocal
from .jobs import crypto_snapshot_job, dolar_job, iol_keepalive, operations_sync, snapshot_job

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _cron(expr: str, tz: str) -> CronTrigger:
    return CronTrigger.from_crontab(expr, timezone=tz)


async def _run_snapshot_and_ops():
    await snapshot_job.run()
    await operations_sync.run()
    try:
        await crypto_snapshot_job.run()
    except Exception:
        log.exception("crypto snapshot job failed")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    db: Session = SessionLocal()
    try:
        enabled = (get_setting(db, "scheduler_enabled", "true") or "true").lower() == "true"
        if not enabled:
            log.info("scheduler disabled via settings")
            return None
        tz = get_setting(db, "tz", "America/Argentina/Buenos_Aires") or "America/Argentina/Buenos_Aires"
        snapshot_cron = get_setting(db, "snapshot_cron", "55 23 * * *") or "55 23 * * *"
        dolar_morning = get_setting(db, "dolar_cron_morning", "0 8 * * *") or "0 8 * * *"
        dolar_evening = get_setting(db, "dolar_cron_evening", "50 23 * * *") or "50 23 * * *"
        keepalive_cron = get_setting(db, "iol_keepalive_cron", "0 */12 * * *") or "0 */12 * * *"
    finally:
        db.close()

    sched = AsyncIOScheduler(timezone=tz)
    sched.add_job(_run_snapshot_and_ops, _cron(snapshot_cron, tz), id="snapshot_and_ops", replace_existing=True)
    sched.add_job(dolar_job.run, _cron(dolar_morning, tz), id="dolar_morning", replace_existing=True)
    sched.add_job(dolar_job.run, _cron(dolar_evening, tz), id="dolar_evening", replace_existing=True)
    sched.add_job(iol_keepalive.run, _cron(keepalive_cron, tz), id="iol_keepalive", replace_existing=True)
    sched.start()
    _scheduler = sched
    log.info("scheduler started tz=%s snapshot=%s keepalive=%s", tz, snapshot_cron, keepalive_cron)
    return sched


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reschedule() -> None:
    stop_scheduler()
    start_scheduler()
