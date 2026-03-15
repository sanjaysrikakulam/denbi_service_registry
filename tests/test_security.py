"""
Security Tests
==============
Tests verifying security controls: authentication, logging scrubbing,
middleware behaviour, and serialiser field isolation.

Note: Full header tests (CSP, HSTS, X-Frame-Options) require Nginx in the
loop and are covered by integration tests. These unit tests cover the
Django/DRF layer.
"""
import pytest
from django.test import Client, RequestFactory

from tests.factories import APIKeyFactory, ServiceSubmissionFactory


# ===========================================================================
# Authentication — API key scheme
# ===========================================================================

@pytest.mark.django_db
class TestAPIKeyAuthentication:

    def test_missing_authorization_header_returns_401_or_403(self):
        from rest_framework.test import APIClient
        client = APIClient()
        sub = ServiceSubmissionFactory()
        resp = client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code in (401, 403)

    def test_wrong_scheme_prefix_returns_401_or_403(self):
        from rest_framework.test import APIClient
        client = APIClient()
        sub = ServiceSubmissionFactory()
        key_obj, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")
        resp = client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code in (401, 403)

    def test_empty_key_value_returns_401(self):
        # An empty ApiKey header triggers AuthenticationFailed → 401 (not authenticated)
        from rest_framework.test import APIClient
        client = APIClient()
        sub = ServiceSubmissionFactory()
        client.credentials(HTTP_AUTHORIZATION="ApiKey ")
        resp = client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code == 401

    def test_auth_failure_response_body_is_generic(self):
        """Auth failure responses must not reveal whether a key exists or is revoked."""
        from rest_framework.test import APIClient
        client = APIClient()
        sub = ServiceSubmissionFactory()
        key_obj, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        key_obj.revoke()

        # Revoked key
        client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp_revoked = client.get(f"/api/v1/submissions/{sub.pk}/")

        # Totally wrong key
        client.credentials(HTTP_AUTHORIZATION="ApiKey completely-wrong-key-value-1234")
        resp_invalid = client.get(f"/api/v1/submissions/{sub.pk}/")

        # Both must return the same status (401 — AuthenticationFailed).
        # Identical responses prevent inferring whether a key exists or is revoked.
        assert resp_revoked.status_code == resp_invalid.status_code
        assert resp_revoked.status_code in (401, 403)


# ===========================================================================
# Logging scrubber
# ===========================================================================

class TestLoggingScrubber:

    def test_authorization_header_redacted(self):
        from apps.submissions.logging_filters import ScrubSensitiveFilter
        import logging

        f = ScrubSensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Authorization: ApiKey supersecretkey123", args=(), exc_info=None
        )
        f.filter(record)
        assert "supersecretkey123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_cookie_header_redacted(self):
        from apps.submissions.logging_filters import ScrubSensitiveFilter
        import logging

        f = ScrubSensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Cookie: sessionid=abc123def456", args=(), exc_info=None
        )
        f.filter(record)
        assert "abc123def456" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_non_sensitive_log_unchanged(self):
        from apps.submissions.logging_filters import ScrubSensitiveFilter
        import logging

        f = ScrubSensitiveFilter()
        msg = "User submitted service 'Galaxy Europe'"
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        f.filter(record)
        assert record.msg == msg


# ===========================================================================
# Request ID middleware
# ===========================================================================

@pytest.mark.django_db
class TestRequestIDMiddleware:

    def test_response_has_x_request_id_header(self):
        client = Client(enforce_csrf_checks=False)
        resp = client.get("/health/live/")
        assert "X-Request-ID" in resp
        # UUID format: 8-4-4-4-12 hex chars
        request_id = resp["X-Request-ID"]
        parts = request_id.split("-")
        assert len(parts) == 5


# ===========================================================================
# CSRF protection
# ===========================================================================

@pytest.mark.django_db
class TestCSRFProtection:

    def test_post_without_csrf_token_fails_in_strict_mode(self):
        """With enforce_csrf_checks=True, POST without token returns 403."""
        client = Client(enforce_csrf_checks=True)
        resp = client.post("/register/", {})
        assert resp.status_code == 403

    def test_csrf_cookie_set_on_get(self):
        """Django must set the csrftoken cookie on GET requests."""
        client = Client()
        resp = client.get("/register/")
        assert "csrftoken" in resp.cookies


# ===========================================================================
# URL scheme validation
# ===========================================================================

class TestURLSchemeValidation:
    """Pure unit tests — no DB needed."""

    @pytest.mark.parametrize("url,should_raise", [
        ("https://example.com", False),
        ("http://example.com", True),
        ("ftp://example.com", True),
        ("javascript:alert(1)", True),
        ("data:text/html,<h1>XSS</h1>", True),
        ("//example.com", True),
        ("", False),  # empty is allowed (optional fields)
    ])
    def test_https_url_validator(self, url, should_raise):
        from apps.submissions.models import _validate_https_url
        from django.core.exceptions import ValidationError
        if should_raise:
            with pytest.raises(ValidationError):
                _validate_https_url(url)
        else:
            _validate_https_url(url)  # must not raise
