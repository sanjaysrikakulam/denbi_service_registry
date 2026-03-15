"""
Management Command: sync_edam
==============================
Downloads the EDAM ontology and upserts all terms into the local EdamTerm table.

Usage:
    python manage.py sync_edam
    python manage.py sync_edam --branch topic
    python manage.py sync_edam --url /path/to/EDAM.owl   # local file
    python manage.py sync_edam --url https://...         # custom URL
    python manage.py sync_edam --dry-run

Default URL (configurable via EDAM_OWL_URL env var or [edam] owl_url in site.toml):
    https://edamontology.org/EDAM_stable.owl
"""

from django.core.management.base import BaseCommand, CommandError

from apps.edam.sync import BRANCH_MAP, run_sync, _default_url


class Command(BaseCommand):
    help = "Download and upsert EDAM ontology terms (OWL/RDF-XML format) into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=None,
            help=(
                f"URL or local file path for EDAM OWL file. "
                f"Defaults to EDAM_OWL_URL env var or {_default_url()}"
            ),
        )
        parser.add_argument(
            "--branch",
            choices=list(BRANCH_MAP.keys()) + ["all"],
            default="all",
            help="Limit sync to a specific EDAM branch (default: all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and count terms but do not write to the database.",
        )

    def handle(self, *args, **options):
        def log(msg):
            self.stdout.write(msg)

        try:
            result = run_sync(
                url=options["url"],
                branch=options["branch"],
                dry_run=options["dry_run"],
                log=log,
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        if not options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"EDAM sync complete. Created: {result['created']}, "
                    f"Updated: {result['updated']}, Total: {result['total']}"
                )
            )
