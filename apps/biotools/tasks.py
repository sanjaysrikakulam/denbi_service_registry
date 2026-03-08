"""
bio.tools Celery Tasks
======================
Periodic and on-demand tasks for syncing bio.tools data.

Tasks:
  sync_biotools_record(submission_id)
      One-off task, called when a submission with a bio.tools URL is saved.

  sync_all_biotools_records()
      Periodic task (Celery beat, daily) that refreshes ALL linked records.
      Runs at 03:00 Europe/Berlin to avoid overlap with EDAM sync.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    name="biotools.sync_record",
)
def sync_biotools_record(self, submission_id: str) -> dict:
    """
    Sync the bio.tools record for a single submission.

    Triggered automatically when a ServiceSubmission with a biotools_url
    is saved (via post_save signal in apps/biotools/signals.py).

    Also callable directly:
        sync_biotools_record.delay(str(submission.id))

    Returns a dict with keys: ok, biotools_id, created, error.
    """
    from apps.submissions.models import ServiceSubmission
    from .sync import sync_tool

    try:
        submission = ServiceSubmission.objects.get(pk=submission_id)
    except ServiceSubmission.DoesNotExist:
        logger.error("sync_biotools_record: submission %s not found", submission_id)
        return {"ok": False, "error": f"Submission {submission_id} not found"}

    if not submission.biotools_url:
        return {"ok": False, "error": "Submission has no bio.tools URL"}

    # Extract the bio.tools ID from the URL: https://bio.tools/<id>
    biotools_id = submission.biotools_url.rstrip("/").split("/")[-1]
    if not biotools_id:
        return {"ok": False, "error": "Could not extract bio.tools ID from URL"}

    logger.info("Syncing bio.tools record: %s for submission %s", biotools_id, submission_id)
    result = sync_tool(biotools_id=biotools_id, submission_id=submission_id)
    return result._asdict()


@shared_task(
    name="biotools.sync_all",
    ignore_result=True,
)
def sync_all_biotools_records() -> None:
    """
    Refresh ALL BioToolsRecord entries from the bio.tools API.

    Scheduled daily (see Celery beat config in config/celery.py).
    Iterates all records and calls sync_tool for each.
    Errors are logged and stored on the record but do not stop the loop.
    """
    from apps.biotools.models import BioToolsRecord
    from .sync import sync_tool

    records = BioToolsRecord.objects.select_related("submission").all()
    total = records.count()
    logger.info("Starting bio.tools bulk sync: %d records", total)

    ok_count = 0
    err_count = 0

    for record in records:
        result = sync_tool(
            biotools_id=record.biotools_id,
            submission_id=str(record.submission_id),
        )
        if result.ok:
            ok_count += 1
        else:
            err_count += 1
            logger.warning(
                "bio.tools sync failed for %s: %s", record.biotools_id, result.error
            )

    logger.info(
        "bio.tools bulk sync complete. OK: %d / %d, Errors: %d",
        ok_count, total, err_count,
    )
