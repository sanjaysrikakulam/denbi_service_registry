import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ServiceCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name shown in the submission form checkbox list.",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive categories are hidden from the submission form but remain associated with existing submissions.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Service Category",
                "verbose_name_plural": "Service Categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ServiceCenter",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "short_name",
                    models.CharField(
                        help_text="Short abbreviation used in lists, e.g. 'HD-HuB', 'BiGi'.",
                        max_length=50,
                    ),
                ),
                (
                    "full_name",
                    models.CharField(
                        help_text="Full official name of the service centre.",
                        max_length=300,
                    ),
                ),
                (
                    "website",
                    models.URLField(
                        blank=True,
                        help_text="URL of the service centre's public website (optional).",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive centres are hidden from the submission form but remain linked to existing submissions.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Service Center",
                "verbose_name_plural": "Service Centers",
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="PrincipalInvestigator",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("last_name", models.CharField(max_length=100)),
                ("first_name", models.CharField(max_length=100)),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        help_text="Contact email for this PI (not publicly visible).",
                        max_length=254,
                    ),
                ),
                (
                    "institute",
                    models.CharField(
                        blank=True,
                        help_text="Home institution of this PI.",
                        max_length=200,
                    ),
                ),
                (
                    "orcid",
                    models.CharField(
                        blank=True,
                        help_text="ORCID iD in format 0000-0000-0000-0000.",
                        max_length=30,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive PIs are hidden from the submission form but remain linked to existing submissions.",
                    ),
                ),
                (
                    "is_associated_partner",
                    models.BooleanField(
                        default=False,
                        help_text="Mark True for the generic 'Associated partner' entry. When selected in the form, the submitter must provide further details.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Principal Investigator",
                "verbose_name_plural": "Principal Investigators",
                "ordering": ["last_name", "first_name"],
            },
        ),
    ]
