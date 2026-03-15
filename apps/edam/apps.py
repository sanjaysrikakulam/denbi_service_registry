import sys

from django.apps import AppConfig


class EdamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.edam"
    verbose_name = "EDAM Ontology"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(_auto_seed_edam, sender=self)


def _auto_seed_edam(sender, **kwargs):
    """
    Seed EDAM terms automatically on first deployment.

    Fires after every `manage.py migrate` run. The check for an empty
    EdamTerm table ensures the download only happens once — on the very
    first migrate against a fresh database. Subsequent runs are no-ops.

    Skipped during test runs (pytest sets sys.modules['pytest']).
    """
    # Never run during test collection or pytest execution
    if "pytest" in sys.modules or "test" in sys.argv:
        return

    try:
        from apps.edam.models import EdamTerm

        if EdamTerm.objects.exists():
            return  # Already seeded — nothing to do

        print(
            "\n[edam] EdamTerm table is empty — running initial EDAM sync.\n"
            "[edam] This downloads ~3 MB from edamontology.org and may take ~30 seconds.\n"
            "[edam] To skip, set EDAM_OWL_URL to a local file path in .env.\n"
        )
        from apps.edam.sync import run_sync

        result = run_sync(log=lambda msg: print(f"[edam] {msg}"))
        print(
            f"[edam] Auto-seed complete — {result['total']} terms loaded "
            f"(EDAM {result['version'] or 'version unknown'}).\n"
        )
    except Exception as exc:
        print(
            f"\n[edam] Auto-seed failed: {exc}\n"
            "[edam] Run manually: python manage.py sync_edam\n"
        )
