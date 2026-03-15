"""
Migration: split submitter_name into first_name, last_name, affiliation.

Data migration strategy:
  The old submitter_name field used the convention "Full Name, Affiliation".
  On upgrade we attempt to parse it:
    - Split on first ", " → left = full name, right = affiliation
    - Split full name on last " " → first + last
  This is best-effort; admins can clean up edge cases via admin.

The old submitter_name field is removed. A @property on the model provides
backwards-compatible read access for any code still using .submitter_name.
"""

from django.db import migrations, models


def split_name_forward(apps, schema_editor):
    ServiceSubmission = apps.get_model("submissions", "ServiceSubmission")
    for sub in ServiceSubmission.objects.all():
        raw = (sub.submitter_name or "").strip()
        if not raw:
            continue
        # Split on first ", " — convention was "Name, Affiliation"
        if ", " in raw:
            name_part, affiliation = raw.split(", ", 1)
        else:
            name_part = raw
            affiliation = ""
        # Split name on last space → first / last
        if " " in name_part:
            idx = name_part.rfind(" ")
            first = name_part[:idx].strip()
            last = name_part[idx:].strip()
        else:
            first = name_part
            last = ""
        sub.submitter_first_name = first
        sub.submitter_last_name = last
        sub.submitter_affiliation = affiliation
        sub.save(
            update_fields=[
                "submitter_first_name",
                "submitter_last_name",
                "submitter_affiliation",
            ]
        )


def split_name_reverse(apps, schema_editor):
    """Reconstruct submitter_name from the split fields on rollback."""
    ServiceSubmission = apps.get_model("submissions", "ServiceSubmission")
    for sub in ServiceSubmission.objects.all():
        parts = []
        name = f"{sub.submitter_first_name} {sub.submitter_last_name}".strip()
        if name:
            parts.append(name)
        if sub.submitter_affiliation:
            parts.append(sub.submitter_affiliation)
        sub.submitter_name = ", ".join(parts)
        sub.save(update_fields=["submitter_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0002_submissionapikey_scope"),
    ]

    operations = [
        # Step 1: add new nullable fields
        migrations.AddField(
            model_name="servicesubmission",
            name="submitter_first_name",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="submitter_last_name",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="servicesubmission",
            name="submitter_affiliation",
            field=models.CharField(default="", max_length=300),
        ),
        # Step 2: populate from old field
        migrations.RunPython(split_name_forward, reverse_code=split_name_reverse),
        # Step 3: remove old field
        migrations.RemoveField(
            model_name="servicesubmission",
            name="submitter_name",
        ),
    ]
