import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("registry", "0001_initial"),
        ("edam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"),
                        ("submitted", "Submitted"),
                        ("under_review", "Under Review"),
                        ("approved", "Approved"),
                        ("rejected", "Rejected"),
                    ],
                    default="submitted",
                    max_length=20,
                )),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("submission_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent_hash", models.CharField(blank=True, max_length=64)),
                # Section A
                ("date_of_entry", models.DateField()),
                ("submitter_name", models.CharField(max_length=300)),
                ("register_as_elixir", models.BooleanField(default=False)),
                # Section B
                ("service_name", models.CharField(max_length=200)),
                ("service_description", models.TextField()),
                ("year_established", models.IntegerField()),
                ("is_toolbox", models.BooleanField(default=False)),
                ("toolbox_name", models.CharField(blank=True, max_length=200)),
                ("user_knowledge_required", models.TextField(blank=True)),
                ("publications_pmids", models.TextField()),
                # Section C
                ("associated_partner_note", models.TextField(blank=True)),
                ("host_institute", models.CharField(max_length=300)),
                ("public_contact_email", models.EmailField(max_length=254)),
                ("internal_contact_name", models.CharField(max_length=300)),
                ("internal_contact_email", models.EmailField(max_length=254)),
                # Section D
                ("website_url", models.URLField(max_length=500)),
                ("terms_of_use_url", models.URLField(max_length=500)),
                ("license", models.CharField(
                    choices=[
                        ("agpl3", "GNU AGPLv3"),
                        ("gpl3", "GNU GPLv3"),
                        ("lgpl3", "GNU LGPLv3"),
                        ("mpl2", "Mozilla Public License 2.0"),
                        ("apache2", "Apache License 2.0"),
                        ("mit", "MIT License"),
                        ("boost", "Boost Software License 1.0"),
                        ("unlicense", "The Unlicense"),
                        ("other", "None of the above"),
                        ("na", "Not applicable"),
                    ],
                    max_length=20,
                )),
                ("github_url", models.URLField(blank=True, max_length=500)),
                ("biotools_url", models.URLField(blank=True, max_length=500)),
                ("fairsharing_url", models.URLField(blank=True, max_length=500)),
                ("other_registry_url", models.URLField(blank=True, max_length=500)),
                # Section E
                ("kpi_monitoring", models.CharField(
                    choices=[("yes", "Yes"), ("no", "No"), ("planned", "Planned")],
                    max_length=10,
                )),
                ("kpi_start_year", models.CharField(blank=True, max_length=4)),
                # Section F
                ("keywords_uncited", models.TextField(blank=True)),
                ("keywords_seo", models.TextField(blank=True)),
                ("outreach_consent", models.BooleanField(default=False)),
                ("survey_participation", models.BooleanField(default=False)),
                ("comments", models.TextField(blank=True)),
                # Section G
                ("data_protection_consent", models.BooleanField(default=False)),
                # ForeignKey
                ("service_center", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="submissions",
                    to="registry.servicecenter",
                )),
            ],
            options={
                "verbose_name": "Service Submission",
                "verbose_name_plural": "Service Submissions",
                "ordering": ["-submitted_at"],
                "indexes": [
                    models.Index(fields=["status"], name="submission_status_idx"),
                    models.Index(fields=["submitted_at"], name="submission_submitted_at_idx"),
                    models.Index(fields=["service_center"], name="submission_service_center_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="service_categories",
            field=models.ManyToManyField(
                help_text="Select all service types that apply.",
                related_name="submissions",
                to="registry.servicecategory",
            ),
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="responsible_pis",
            field=models.ManyToManyField(
                help_text="PI(s) responsible for this service.",
                related_name="submissions",
                to="registry.principalinvestigator",
            ),
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="edam_topics",
            field=models.ManyToManyField(
                blank=True,
                help_text="EDAM Topic terms describing the scientific domain of this service.",
                limit_choices_to={"branch": "topic", "is_obsolete": False},
                related_name="submissions_by_topic",
                to="edam.edamterm",
            ),
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="edam_operations",
            field=models.ManyToManyField(
                blank=True,
                help_text="EDAM Operation terms describing what this service does.",
                limit_choices_to={"branch": "operation", "is_obsolete": False},
                related_name="submissions_by_operation",
                to="edam.edamterm",
            ),
        ),
        migrations.CreateModel(
            name="SubmissionAPIKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("submission", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="api_keys",
                    to="submissions.servicesubmission",
                )),
                ("key_hash", models.CharField(max_length=64)),
                ("label", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Submission API Key",
                "verbose_name_plural": "Submission API Keys",
                "ordering": ["-created_at"],
            },
        ),
    ]
