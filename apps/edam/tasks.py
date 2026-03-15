"""Celery tasks for EDAM ontology sync."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="edam.sync", bind=True, max_retries=2, default_retry_delay=300)
def sync_edam_task(self, url: str | None = None) -> dict:
    """
    Download and upsert EDAM ontology terms.

    Triggered by:
    - Admin "Sync EDAM" button (immediate)
    - Celery beat monthly schedule
    """
    from apps.edam.sync import run_sync

    try:
        return run_sync(url=url, log=logger.info)
    except Exception as exc:
        logger.exception("EDAM sync failed: %s", exc)
        raise self.retry(exc=exc)
