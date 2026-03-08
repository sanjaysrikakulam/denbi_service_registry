from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EdamTerm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uri", models.URLField(db_index=True, help_text="Full EDAM URI, e.g. http://edamontology.org/topic_0091.", max_length=200, unique=True)),
                ("accession", models.CharField(db_index=True, help_text="Short EDAM accession, e.g. topic_0091.", max_length=40, unique=True)),
                ("branch", models.CharField(
                    choices=[
                        ("topic", "Topic"),
                        ("operation", "Operation"),
                        ("data", "Data"),
                        ("format", "Format"),
                        ("identifier", "Identifier"),
                    ],
                    db_index=True,
                    help_text="Top-level EDAM branch this term belongs to.",
                    max_length=20,
                )),
                ("label", models.CharField(db_index=True, help_text="Human-readable preferred label, e.g. 'Proteomics'.", max_length=200)),
                ("definition", models.TextField(blank=True, help_text="EDAM definition text for this term.")),
                ("synonyms", models.JSONField(default=list, help_text="List of synonym strings for search augmentation.")),
                ("is_obsolete", models.BooleanField(default=False, help_text="Obsolete terms are hidden from form dropdowns but retained for historical records.")),
                ("sort_order", models.PositiveIntegerField(default=0, help_text="Numeric part of the accession; used for stable ordering within a branch.")),
                ("edam_version", models.CharField(blank=True, help_text="EDAM release version this term was last updated from, e.g. '1.25'.", max_length=20)),
                ("parent", models.ForeignKey(
                    blank=True,
                    help_text="Direct parent term in the EDAM hierarchy.",
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="children",
                    to="edam.edamterm",
                )),
            ],
            options={
                "verbose_name": "EDAM Term",
                "verbose_name_plural": "EDAM Terms",
                "ordering": ["branch", "sort_order"],
                "indexes": [
                    models.Index(fields=["branch", "is_obsolete"], name="edam_term_branch_obsolete_idx"),
                    models.Index(fields=["label"], name="edam_term_label_idx"),
                ],
            },
        ),
    ]
