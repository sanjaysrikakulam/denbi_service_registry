"""
Async Tasks
===========
Celery tasks for background processing — primarily email notifications.

Tasks:
  - send_submission_notification : Email admin on new submission or status change
  - send_update_notification     : Email admin when a submitter edits a submission
  - cleanup_stale_drafts         : Periodic task to remove expired draft sessions
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Retry after 60 seconds
    autoretry_for=(Exception,),
)
def send_submission_notification(self, submission_id: str, event: str = "created") -> None:
    """
    Send an email notification to the internal contact for a submission.

    Called:
      - When a new submission is created (event="created")
      - When the admin changes the submission status (event="status_changed")

    The email contains the full submission summary but never the API key.

    Args:
        submission_id: UUID string of the ServiceSubmission
        event: "created" | "status_changed"
    """
    from apps.submissions.models import ServiceSubmission

    try:
        submission = ServiceSubmission.objects.select_related(
            "service_center"
        ).prefetch_related(
            "service_categories", "responsible_pis"
        ).get(id=submission_id)
    except ServiceSubmission.DoesNotExist:
        logger.error(f"send_submission_notification: submission {submission_id} not found")
        return

    # Primary recipient: admin contact from site.toml (the registry coordinators)
    # CC the submitter's internal contact email so they also receive a copy
    admin_email = getattr(settings, "SITE_CONFIG", {}).get("contact", {}).get("email", "")
    override = getattr(settings, "SUBMISSION_NOTIFY_OVERRIDE", "")
    recipient = override or admin_email or settings.DEFAULT_FROM_EMAIL

    # CC the internal contact of the submission so they have a record too
    cc_submitter = submission.internal_contact_email

    cc_list = list(getattr(settings, "SUBMISSION_NOTIFY_CC", []))
    if cc_submitter and cc_submitter != recipient:
        cc_list.append(cc_submitter)

    subject_map = {
        "created": f"[de.NBI Registry] New service submission: {submission.service_name}",
        "status_changed": (
            f"[de.NBI Registry] Status updated to '{submission.get_status_display()}': "
            f"{submission.service_name}"
        ),
    }
    subject = subject_map.get(event, f"[de.NBI Registry] Update: {submission.service_name}")

    context = {
        "submission": submission,
        "event": event,
        "categories": list(submission.service_categories.values_list("name", flat=True)),
        "pis": list(submission.responsible_pis.all()),
    }

    text_body = render_to_string("submissions/email/notification.txt", context)
    html_body = render_to_string("submissions/email/notification.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        cc=cc_list,
        reply_to=[settings.DEFAULT_FROM_EMAIL],
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send(fail_silently=False)
        logger.info(
            f"Notification sent for submission {submission_id}",
            extra={"event": event, "recipient": recipient},
        )
    except Exception as exc:
        logger.error(f"Failed to send notification for {submission_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def send_update_notification(self, submission_id: str) -> None:
    """
    Send notification when a submitter edits their submission via the update form.

    Includes a summary of the updated values and the timestamp.
    """
    send_submission_notification.delay(submission_id, event="updated")


@shared_task
def cleanup_stale_drafts() -> int:
    """
    Remove Django session entries that were used for draft auto-save and
    have not been accessed in more than 24 hours.

    Returns the number of sessions cleaned up.
    """
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session

    cutoff = timezone.now() - timedelta(hours=24)
    stale = Session.objects.filter(expire_date__lt=cutoff)
    count = stale.count()
    stale.delete()
    logger.info(f"cleanup_stale_drafts: removed {count} expired sessions")
    return count
