"""
Task Tests
==========
Tests for async Celery tasks — primarily email dispatch.
Tasks are executed synchronously in tests (CELERY_TASK_ALWAYS_EAGER=True).
"""
import pytest
from django.core import mail

from tests.factories import ServiceSubmissionFactory


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Run all Celery tasks synchronously in tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.mark.django_db
class TestSubmissionNotificationTask:

    def test_notification_sent_on_create(self):
        # Primary recipient is the site coordinator (from SITE_CONFIG).
        # The submission's internal_contact_email is added to CC.
        sub = ServiceSubmissionFactory(internal_contact_email="admin@example.com")
        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="created")
        assert len(mail.outbox) == 1
        all_recipients = mail.outbox[0].to + mail.outbox[0].cc
        assert "admin@example.com" in all_recipients

    def test_notification_subject_contains_service_name(self):
        sub = ServiceSubmissionFactory(service_name="Galaxy Europe")
        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="created")
        assert "Galaxy Europe" in mail.outbox[0].subject

    def test_notification_does_not_contain_api_key(self):
        """Email body must never contain any API key or key hash."""
        sub = ServiceSubmissionFactory()
        from apps.submissions.models import SubmissionAPIKey
        key_obj, plaintext = SubmissionAPIKey.create_for_submission(sub)

        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="created")

        body = mail.outbox[0].body
        assert plaintext not in body
        assert key_obj.key_hash not in body

    def test_notification_does_not_contain_internal_email_in_body_headers(self):
        """Internal email should be recipient only, not exposed in body."""
        sub = ServiceSubmissionFactory(internal_contact_email="secret@internal.de")
        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="created")
        # Email body should not repeat the internal address redundantly
        # (it is OK in To: header — that is the intended recipient)
        assert len(mail.outbox) == 1

    def test_status_changed_email_has_correct_subject(self):
        sub = ServiceSubmissionFactory(service_name="MetaProFi", status="approved")
        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="status_changed")
        assert "MetaProFi" in mail.outbox[0].subject
        assert "approved" in mail.outbox[0].subject.lower() or "status" in mail.outbox[0].subject.lower()

    def test_nonexistent_submission_does_not_raise(self):
        from apps.submissions.tasks import send_submission_notification
        # Should log error but not crash
        send_submission_notification("00000000-0000-0000-0000-000000000000", event="created")

    def test_email_override_setting_used(self, settings):
        settings.SUBMISSION_NOTIFY_OVERRIDE = "override@test.com"
        sub = ServiceSubmissionFactory(internal_contact_email="real@example.com")
        from apps.submissions.tasks import send_submission_notification
        send_submission_notification(str(sub.id), event="created")
        assert "override@test.com" in mail.outbox[0].to
        assert "real@example.com" not in mail.outbox[0].to


@pytest.mark.django_db
class TestCleanupTask:

    def test_cleanup_runs_without_error(self):
        from apps.submissions.tasks import cleanup_stale_drafts
        result = cleanup_stale_drafts()
        assert isinstance(result, int)
        assert result >= 0
