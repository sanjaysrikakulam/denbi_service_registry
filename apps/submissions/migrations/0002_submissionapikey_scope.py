"""
Add scope field to SubmissionAPIKey.
Default is 'write' to preserve existing key behaviour.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="submissionapikey",
            name="scope",
            field=models.CharField(
                choices=[
                    ("read", "Read-only  (GET retrieve only)"),
                    ("write", "Read-write (GET retrieve + PATCH update)"),
                ],
                default="write",
                help_text="'read' = GET only; 'write' = GET + PATCH.",
                max_length=10,
            ),
        ),
    ]
