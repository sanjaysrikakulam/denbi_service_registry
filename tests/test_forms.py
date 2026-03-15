"""
Form Tests
==========
Tests for SubmissionForm and UpdateKeyForm validation logic.
Covers required fields, cross-field rules, URL scheme enforcement,
email confirmation matching, and conditional field visibility.
"""

import pytest

from tests.factories import PIFactory, ServiceCategoryFactory, ServiceCenterFactory


def _base_form_data(overrides=None):
    """Return a dict of minimal valid POST data for SubmissionForm."""
    from django.utils import timezone

    cat = ServiceCategoryFactory()
    center = ServiceCenterFactory()
    pi = PIFactory()

    data = {
        # Section A
        "date_of_entry": timezone.now().date().isoformat(),
        "submitter_first_name": "Test",
        "submitter_last_name": "Researcher",
        "submitter_affiliation": "Test University",
        "register_as_elixir": False,
        # Section B
        "service_name": "Test Service",
        "service_description": "A detailed description of the test service exceeding fifty characters minimum.",
        "year_established": 2020,
        "service_categories": [cat.pk],
        "is_toolbox": False,
        "toolbox_name": "",
        "user_knowledge_required": "",
        "publications_pmids": "12345678",
        # Section C
        "responsible_pis": [pi.pk],
        "associated_partner_note": "",
        "host_institute": "Test Institute",
        "service_center": center.pk,
        "public_contact_email": "public@example.com",
        "internal_contact_name": "Test Contact, Institute",
        "internal_contact_email": "internal@example.com",
        "internal_contact_email_confirm": "internal@example.com",
        # Section D
        "website_url": "https://example.com",
        "terms_of_use_url": "https://example.com/tos",
        "license": "mit",
        "github_url": "",
        "biotools_url": "",
        "fairsharing_url": "",
        "other_registry_url": "",
        # Section E
        "kpi_monitoring": "yes",
        "kpi_start_year": "2021",
        # Section F
        "keywords_uncited": "",
        "keywords_seo": "",
        "outreach_consent": True,
        "survey_participation": True,
        "comments": "",
        # Section G
        "data_protection_consent": True,
    }
    if overrides:
        data.update(overrides)
    return data


@pytest.mark.django_db
class TestSubmissionFormValid:
    def test_minimal_valid_form_passes(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(_base_form_data())
        assert form.is_valid(), form.errors

    def test_elixir_registration_optional(self):
        from apps.submissions.forms import SubmissionForm

        for val in (True, False):
            form = SubmissionForm(_base_form_data({"register_as_elixir": val}))
            assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestSubmissionFormRequired:
    @pytest.mark.parametrize(
        "field",
        [
            "service_name",
            "service_description",
            "submitter_first_name",
            "submitter_last_name",
            "submitter_affiliation",
            "host_institute",
            "public_contact_email",
            "internal_contact_name",
            "internal_contact_email",
            "internal_contact_email_confirm",
            "website_url",
            "terms_of_use_url",
            "publications_pmids",
        ],
    )
    def test_required_field_blank_fails(self, field):
        from apps.submissions.forms import SubmissionForm

        data = _base_form_data({field: ""})
        form = SubmissionForm(data)
        assert not form.is_valid()
        assert field in form.errors

    def test_data_protection_consent_required(self):
        from apps.submissions.forms import SubmissionForm

        data = _base_form_data({"data_protection_consent": False})
        form = SubmissionForm(data)
        assert not form.is_valid()
        assert "data_protection_consent" in form.errors


@pytest.mark.django_db
class TestSubmissionFormCrossField:
    def test_toolbox_name_required_when_is_toolbox_true(self):
        from apps.submissions.forms import SubmissionForm

        data = _base_form_data({"is_toolbox": True, "toolbox_name": ""})
        form = SubmissionForm(data)
        assert not form.is_valid()
        assert "toolbox_name" in form.errors

    def test_toolbox_name_accepted_when_is_toolbox_true(self):
        from apps.submissions.forms import SubmissionForm

        data = _base_form_data({"is_toolbox": True, "toolbox_name": "de.NBI Toolbox"})
        form = SubmissionForm(data)
        assert form.is_valid(), form.errors

    def test_email_confirmation_must_match(self):
        from apps.submissions.forms import SubmissionForm

        data = _base_form_data(
            {
                "internal_contact_email": "a@example.com",
                "internal_contact_email_confirm": "b@example.com",
            }
        )
        form = SubmissionForm(data)
        assert not form.is_valid()
        assert "internal_contact_email_confirm" in form.errors

    def test_associated_partner_note_required_when_pi_is_partner(self):
        """When the 'associated partner' PI is selected, a note is required."""
        from apps.submissions.forms import SubmissionForm
        from tests.factories import AssociatedPartnerPIFactory

        partner_pi = AssociatedPartnerPIFactory()
        data = _base_form_data(
            {
                "responsible_pis": [partner_pi.pk],
                "associated_partner_note": "",
            }
        )
        form = SubmissionForm(data)
        assert not form.is_valid()
        assert "associated_partner_note" in form.errors


@pytest.mark.django_db
class TestSubmissionFormURLValidation:
    def test_http_website_url_rejected(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(_base_form_data({"website_url": "http://example.com"}))
        assert not form.is_valid()
        assert "website_url" in form.errors

    def test_https_website_url_accepted(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(_base_form_data({"website_url": "https://example.com"}))
        assert form.is_valid(), form.errors

    def test_github_url_must_be_github(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(
            _base_form_data({"github_url": "https://gitlab.com/org/repo"})
        )
        assert not form.is_valid()
        assert "github_url" in form.errors

    def test_biotools_url_must_be_biotools(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(
            _base_form_data({"biotools_url": "https://bioinformatics.tools/x"})
        )
        assert not form.is_valid()
        assert "biotools_url" in form.errors

    def test_optional_urls_blank_accepted(self):
        from apps.submissions.forms import SubmissionForm

        form = SubmissionForm(
            _base_form_data(
                {
                    "github_url": "",
                    "biotools_url": "",
                    "fairsharing_url": "",
                    "other_registry_url": "",
                }
            )
        )
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestUpdateKeyForm:
    def test_empty_key_rejected(self):
        from apps.submissions.forms import UpdateKeyForm

        form = UpdateKeyForm({"api_key": ""})
        assert not form.is_valid()

    def test_very_short_key_rejected(self):
        from apps.submissions.forms import UpdateKeyForm

        form = UpdateKeyForm({"api_key": "short"})
        assert not form.is_valid()

    def test_valid_length_key_accepted(self):
        import secrets
        from apps.submissions.forms import UpdateKeyForm

        key = secrets.token_urlsafe(48)
        form = UpdateKeyForm({"api_key": key})
        assert form.is_valid(), form.errors
