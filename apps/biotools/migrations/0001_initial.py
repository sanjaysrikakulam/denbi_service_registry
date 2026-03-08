import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("submissions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BioToolsRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("submission", models.OneToOneField(
                    help_text="The de.NBI service registration this bio.tools record belongs to.",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="biotoolsrecord",
                    to="submissions.servicesubmission",
                )),
                ("biotools_id", models.CharField(db_index=True, help_text="bio.tools tool ID, e.g. 'blast' or 'interproscan'.", max_length=200)),
                ("name", models.CharField(blank=True, help_text="Tool name as it appears in bio.tools.", max_length=200)),
                ("description", models.TextField(blank=True, help_text="Tool description from bio.tools.")),
                ("homepage", models.URLField(blank=True, help_text="Tool homepage URL from bio.tools.")),
                ("version", models.CharField(blank=True, help_text="Latest version string from bio.tools.", max_length=100)),
                ("license", models.CharField(blank=True, help_text="SPDX license identifier from bio.tools.", max_length=100)),
                ("maturity", models.CharField(blank=True, max_length=50)),
                ("cost", models.CharField(blank=True, max_length=50)),
                ("tool_type", models.JSONField(default=list, help_text="List of bio.tools toolType values.")),
                ("operating_system", models.JSONField(default=list, help_text="List of operating system names from bio.tools.")),
                ("publications", models.JSONField(default=list, help_text="Publications from bio.tools (list of {pmid, doi, pmcid, type}).")),
                ("documentation", models.JSONField(default=list, help_text="Documentation links from bio.tools.")),
                ("download", models.JSONField(default=list, help_text="Download links from bio.tools.")),
                ("links", models.JSONField(default=list, help_text="Other links from bio.tools.")),
                ("edam_topic_uris", models.JSONField(default=list, help_text="List of EDAM topic URIs from bio.tools.")),
                ("raw_json", models.JSONField(help_text="Complete raw API response from bio.tools, stored verbatim.")),
                ("last_synced_at", models.DateTimeField(blank=True, help_text="When this record was last refreshed from the bio.tools API.", null=True)),
                ("sync_error", models.TextField(blank=True, help_text="Last sync error message, if any.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "bio.tools Record",
                "verbose_name_plural": "bio.tools Records",
                "ordering": ["biotools_id"],
            },
        ),
        migrations.CreateModel(
            name="BioToolsFunction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("record", models.ForeignKey(
                    help_text="The bio.tools record this function block belongs to.",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="functions",
                    to="biotools.biotoolsrecord",
                )),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("operations", models.JSONField(default=list, help_text="EDAM Operation annotations: [{uri, term}, ...].")),
                ("inputs", models.JSONField(default=list, help_text="Input data/format annotations from bio.tools.")),
                ("outputs", models.JSONField(default=list, help_text="Output data/format annotations from bio.tools.")),
                ("cmd", models.TextField(blank=True, help_text="Command-line note from bio.tools (if any).")),
                ("note", models.TextField(blank=True, help_text="Free-text note for this function from bio.tools.")),
            ],
            options={
                "verbose_name": "bio.tools Function",
                "verbose_name_plural": "bio.tools Functions",
                "ordering": ["record", "position"],
                "unique_together": {("record", "position")},
            },
        ),
    ]
