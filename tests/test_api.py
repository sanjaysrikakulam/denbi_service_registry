"""
API Tests
=========
Tests for the DRF REST API endpoints.

Coverage:
  POST   /api/v1/submissions/        create, one-time key, consent, field validation
  GET    /api/v1/submissions/        admin list, pagination, filtering, full detail
  GET    /api/v1/submissions/{id}/   own submission only, wrong key denied, full detail shape
  PATCH  /api/v1/submissions/{id}/   partial update, status reset on approved
  PUT    /api/v1/submissions/{id}/   forbidden (405)
  GET    /api/v1/categories/         admin token required, active-only
  GET    /api/v1/service-centers/    admin token required, active-only
  GET    /api/v1/pis/                admin token required, active-only
  GET    /api/schema/                always 200
  GET    /api/docs/                  always 200
  Auth:  ApiKey vs Token, revoked denial, scope enforcement, no-auth denial
  Shape: links present, sensitive fields absent, EDAM embedded, bio.tools embedded
"""

import pytest
from rest_framework.test import APIClient

from tests.factories import (
    APIKeyFactory,
    PIFactory,
    ServiceCategoryFactory,
    ServiceCenterFactory,
    ServiceSubmissionFactory,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    from django.contrib.auth import get_user_model
    from rest_framework.authtoken.models import Token

    User = get_user_model()
    user = User.objects.create_user(
        username="admin_test", password="testpass123", is_staff=True, is_active=True
    )
    token = Token.objects.create(user=user)
    return user, token.key


@pytest.fixture
def staff_client(api_client, admin_user):
    _, token = admin_user
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    return api_client


def _valid_payload():
    """Return a complete, valid POST payload for submission creation."""
    cat = ServiceCategoryFactory()
    center = ServiceCenterFactory()
    pi = PIFactory()
    from django.utils import timezone

    return {
        "date_of_entry": timezone.now().date().isoformat(),
        "submitter_first_name": "API Test",
        "submitter_last_name": "User",
        "submitter_affiliation": "API Institute",
        "register_as_elixir": False,
        "service_name": "API Created Service",
        "service_description": (
            "A description created via the API that is long enough to pass "
            "validation checks imposed by the model's minimum length constraint."
        ),
        "year_established": 2021,
        "service_category_ids": [cat.pk],
        "is_toolbox": False,
        "publications_pmids": "12345678",
        "responsible_pi_ids": [str(pi.pk)],
        "host_institute": "API Institute",
        "service_center_id": str(center.pk),
        "public_contact_email": "api@example.com",
        "internal_contact_name": "API Contact",
        "internal_contact_email": "api-internal@example.com",
        "website_url": "https://api.example.com",
        "terms_of_use_url": "https://api.example.com/tos",
        "license": "apache2",
        "kpi_monitoring": "planned",
        "kpi_start_year": "2021",
        "outreach_consent": True,
        "survey_participation": True,
        "data_protection_consent": True,
    }


# ===========================================================================
# POST /api/v1/submissions/ — public, no auth
# ===========================================================================


@pytest.mark.django_db
class TestSubmissionCreate:
    def test_create_returns_201(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        assert resp.status_code == 201

    def test_create_response_contains_api_key(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        data = resp.json()
        assert "api_key" in data
        assert len(data["api_key"]) >= 48

    def test_create_response_contains_api_key_warning(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        assert "api_key_warning" in resp.json()

    def test_create_response_has_links(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        data = resp.json()
        assert "links" in data
        assert "self" in data["links"]

    def test_create_empty_payload_returns_400(self, api_client):
        resp = api_client.post("/api/v1/submissions/", {}, format="json")
        assert resp.status_code == 400

    def test_create_no_consent_returns_400(self, api_client):
        payload = _valid_payload()
        payload["data_protection_consent"] = False
        resp = api_client.post("/api/v1/submissions/", payload, format="json")
        assert resp.status_code == 400

    def test_create_http_url_returns_400(self, api_client):
        payload = _valid_payload()
        payload["website_url"] = "http://not-https.com"
        resp = api_client.post("/api/v1/submissions/", payload, format="json")
        assert resp.status_code == 400

    def test_create_response_excludes_internal_email(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        data = resp.json()
        assert "internal_contact_email" not in data
        assert "api-internal@example.com" not in str(data)

    def test_create_response_excludes_submission_ip(self, api_client):
        resp = api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        assert "submission_ip" not in resp.json()

    def test_create_creates_api_key_in_db(self, api_client):
        from apps.submissions.models import SubmissionAPIKey

        before = SubmissionAPIKey.objects.count()
        api_client.post("/api/v1/submissions/", _valid_payload(), format="json")
        assert SubmissionAPIKey.objects.count() == before + 1

    def test_create_error_envelope_on_invalid(self, api_client):
        resp = api_client.post("/api/v1/submissions/", {}, format="json")
        data = resp.json()
        assert "error" in data
        assert "request_id" in data


# ===========================================================================
# GET /api/v1/submissions/{id}/ — ApiKey auth, full detail
# ===========================================================================


@pytest.mark.django_db
class TestSubmissionRetrieve:
    def test_retrieve_own_submission_with_valid_key(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(sub.pk)

    def test_retrieve_returns_edam_topics(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        data = resp.json()
        assert "edam_topics" in data
        assert "edam_operations" in data
        assert isinstance(data["edam_topics"], list)

    def test_retrieve_returns_biotoolsrecord_field(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        data = resp.json()
        assert "biotoolsrecord" in data  # null if not synced, present either way

    def test_retrieve_returns_responsible_pis(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        data = resp.json()
        assert "responsible_pis" in data
        assert isinstance(data["responsible_pis"], list)

    def test_retrieve_fails_without_auth(self, api_client):
        sub = ServiceSubmissionFactory()
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code in (401, 403)

    def test_retrieve_fails_with_wrong_key(self, api_client):
        sub_a = ServiceSubmissionFactory(service_name="Sub A")
        sub_b = ServiceSubmissionFactory(service_name="Sub B")
        _, key_b = APIKeyFactory.create_with_plaintext(submission=sub_b)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {key_b}")
        resp = api_client.get(f"/api/v1/submissions/{sub_a.pk}/")
        assert resp.status_code in (403, 404)

    def test_retrieve_fails_with_revoked_key(self, api_client):
        sub = ServiceSubmissionFactory()
        key_obj, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        key_obj.revoke()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        # AuthenticationFailed raises 401; both 401 and 403 are acceptable rejections
        assert resp.status_code in (401, 403)

    def test_retrieve_response_excludes_sensitive_fields(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        data = resp.json()
        for field in (
            "internal_contact_email",
            "internal_contact_name",
            "submission_ip",
            "user_agent_hash",
        ):
            assert field not in data


# ===========================================================================
# PATCH /api/v1/submissions/{id}/ — scope enforcement
# ===========================================================================


@pytest.mark.django_db
class TestSubmissionUpdate:
    def test_patch_own_submission(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.patch(
            f"/api/v1/submissions/{sub.pk}/",
            {"kpi_start_year": "2025"},
            format="json",
        )
        assert resp.status_code == 200
        sub.refresh_from_db()
        assert sub.kpi_start_year == "2025"

    def test_patch_rejected_without_auth(self, api_client):
        sub = ServiceSubmissionFactory()
        resp = api_client.patch(f"/api/v1/submissions/{sub.pk}/", {}, format="json")
        assert resp.status_code in (401, 403)

    def test_patch_rejected_with_read_only_key(self, api_client):
        """Read-scoped ApiKey must not be able to PATCH."""
        from apps.submissions.models import SubmissionAPIKey

        sub = ServiceSubmissionFactory()
        key_obj, plaintext = SubmissionAPIKey.create_for_submission(
            submission=sub, label="RO key", created_by="test", scope="read"
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.patch(
            f"/api/v1/submissions/{sub.pk}/",
            {"comments": "should fail"},
            format="json",
        )
        assert resp.status_code == 403

    def test_read_only_key_can_get(self, api_client):
        """Read-scoped ApiKey must be able to GET."""
        from apps.submissions.models import SubmissionAPIKey

        sub = ServiceSubmissionFactory()
        _, plaintext = SubmissionAPIKey.create_for_submission(
            submission=sub, label="RO key", created_by="test", scope="read"
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get(f"/api/v1/submissions/{sub.pk}/")
        assert resp.status_code == 200

    def test_put_rejected(self, api_client):
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.put(f"/api/v1/submissions/{sub.pk}/", {}, format="json")
        assert resp.status_code == 405

    def test_patch_approved_submission_resets_status(self, api_client):
        sub = ServiceSubmissionFactory(status="approved")
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.patch(
            f"/api/v1/submissions/{sub.pk}/",
            {"comments": "Updated after approval"},
            format="json",
        )
        assert resp.status_code == 200
        sub.refresh_from_db()
        assert sub.status == "submitted"


# ===========================================================================
# GET /api/v1/submissions/ — admin list, full detail
# ===========================================================================


@pytest.mark.django_db
class TestSubmissionList:
    def test_list_requires_admin_token(self, api_client):
        resp = api_client.get("/api/v1/submissions/")
        assert resp.status_code in (401, 403)

    def test_list_apikey_auth_denied(self, api_client):
        """ApiKey must not grant access to the list endpoint."""
        sub = ServiceSubmissionFactory()
        _, plaintext = APIKeyFactory.create_with_plaintext(submission=sub)
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        resp = api_client.get("/api/v1/submissions/")
        assert resp.status_code == 403

    def test_list_with_admin_token_returns_200(self, staff_client):
        ServiceSubmissionFactory.create_batch(3)
        resp = staff_client.get("/api/v1/submissions/")
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_list_returns_full_detail_fields(self, staff_client):
        """List endpoint returns full detail — not a compact summary."""
        ServiceSubmissionFactory()
        resp = staff_client.get("/api/v1/submissions/")
        item = resp.json()["results"][0]
        for field in (
            "edam_topics",
            "edam_operations",
            "responsible_pis",
            "biotoolsrecord",
            "website_url",
            "license",
            "kpi_monitoring",
        ):
            assert field in item, f"Missing field: {field}"

    def test_list_filtered_by_status(self, staff_client):
        ServiceSubmissionFactory(status="approved")
        ServiceSubmissionFactory(status="submitted")
        resp = staff_client.get("/api/v1/submissions/?status=approved")
        for item in resp.json()["results"]:
            assert item["status"] == "approved"

    def test_list_excludes_internal_contact_email(self, staff_client):
        ServiceSubmissionFactory(internal_contact_email="secret@example.com")
        resp = staff_client.get("/api/v1/submissions/")
        assert "secret@example.com" not in resp.content.decode()

    def test_list_paginated(self, staff_client):
        ServiceSubmissionFactory.create_batch(5)
        resp = staff_client.get("/api/v1/submissions/?page_size=2")
        data = resp.json()
        assert "count" in data
        assert "next" in data


# ===========================================================================
# Reference data endpoints
# ===========================================================================


@pytest.mark.django_db
class TestReferenceDataEndpoints:
    def test_categories_requires_admin_token(self, api_client):
        resp = api_client.get("/api/v1/categories/")
        assert resp.status_code in (401, 403)

    def test_categories_returns_active_only(self, staff_client):
        ServiceCategoryFactory(name="Active Cat", is_active=True)
        ServiceCategoryFactory(name="Inactive Cat", is_active=False)
        resp = staff_client.get("/api/v1/categories/")
        names = [c["name"] for c in resp.json()]
        assert "Active Cat" in names
        assert "Inactive Cat" not in names

    def test_service_centers_requires_admin_token(self, api_client):
        resp = api_client.get("/api/v1/service-centers/")
        assert resp.status_code in (401, 403)

    def test_pis_requires_admin_token(self, api_client):
        resp = api_client.get("/api/v1/pis/")
        assert resp.status_code in (401, 403)

    def test_pis_returns_active_only(self, staff_client):
        PIFactory(last_name="ActivePI", is_active=True)
        PIFactory(last_name="InactivePI", is_active=False)
        resp = staff_client.get("/api/v1/pis/")
        last_names = [p["last_name"] for p in resp.json()]
        assert "ActivePI" in last_names
        assert "InactivePI" not in last_names

    def test_pi_response_has_display_name(self, staff_client):
        PIFactory(first_name="Ada", last_name="Lovelace", is_active=True)
        resp = staff_client.get("/api/v1/pis/")
        pi = next(p for p in resp.json() if p["last_name"] == "Lovelace")
        assert "display_name" in pi
        assert "Lovelace" in pi["display_name"]


# ===========================================================================
# EDAM endpoint — public
# ===========================================================================


@pytest.mark.django_db
class TestEdamEndpoint:
    def test_edam_list_is_public(self, api_client):
        resp = api_client.get("/api/v1/edam/")
        assert resp.status_code == 200

    def test_edam_filter_by_branch(self, api_client):
        from apps.edam.models import EdamTerm

        # Only run if EDAM data is loaded; skip otherwise
        if not EdamTerm.objects.exists():
            pytest.skip("EDAM data not loaded")
        resp = api_client.get("/api/v1/edam/?branch=topic")
        for term in resp.json():
            assert term["branch"] == "topic"


# ===========================================================================
# OpenAPI / docs endpoints
# ===========================================================================


@pytest.mark.django_db
class TestOpenAPIEndpoints:
    def test_schema_returns_200(self, api_client):
        resp = api_client.get("/api/schema/")
        assert resp.status_code == 200

    def test_swagger_ui_returns_200(self, api_client):
        resp = api_client.get("/api/docs/")
        assert resp.status_code == 200

    def test_redoc_returns_200(self, api_client):
        resp = api_client.get("/api/redoc/")
        assert resp.status_code == 200

    def test_schema_mentions_apikey_auth(self, api_client):
        resp = api_client.get("/api/schema/")
        assert b"ApiKey" in resp.content or b"apiKey" in resp.content


# ===========================================================================
# Error envelope consistency
# ===========================================================================


@pytest.mark.django_db
class TestErrorEnvelope:
    def test_auth_error_has_envelope(self, api_client):
        resp = api_client.get("/api/v1/submissions/")
        data = resp.json()
        assert "error" in data
        assert "request_id" in data

    def test_not_found_has_envelope(self, api_client, admin_user):
        _, token = admin_user
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        resp = api_client.get(
            "/api/v1/submissions/00000000-0000-0000-0000-000000000000/"
        )
        data = resp.json()
        assert "error" in data
        assert "request_id" in data
