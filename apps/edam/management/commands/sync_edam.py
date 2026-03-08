"""
Management Command: sync_edam
==============================
Downloads the EDAM ontology and upserts all terms into the local EdamTerm table.

The EDAM ontology is distributed as an OWL/RDF-XML file. The stable release URL
is configurable via the EDAM_OWL_URL environment variable (see .env.example).

Usage:
    python manage.py sync_edam
    python manage.py sync_edam --branch topic
    python manage.py sync_edam --url /path/to/EDAM.owl   # local file
    python manage.py sync_edam --url https://...         # custom URL
    python manage.py sync_edam --dry-run

Default URL (configurable via EDAM_OWL_URL env var):
    https://edamontology.org/EDAM_stable.owl
"""
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

# RDF/OWL namespace URIs used in EDAM
RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL  = "http://www.w3.org/2002/07/owl#"
OBOINOWL = "http://www.geneontology.org/formats/oboInOwl#"
EDAM_BASE = "http://edamontology.org/"

# Read from Django settings (which layers site.toml → env var → hardcoded fallback)
try:
    from django.conf import settings as _django_settings
    DEFAULT_EDAM_URL = getattr(_django_settings, "EDAM_OWL_URL", "https://edamontology.org/EDAM_stable.owl")
except Exception:
    DEFAULT_EDAM_URL = os.environ.get("EDAM_OWL_URL", "https://edamontology.org/EDAM_stable.owl")

BRANCH_MAP = {
    "topic":      "topic",
    "operation":  "operation",
    "data":       "data",
    "format":     "format",
    "identifier": "identifier",
}


def _tag(ns, local):
    return f"{{{ns}}}{local}"


def _extract_accession(uri: str) -> str | None:
    match = re.search(r"/([\w]+_\d+)$", uri)
    return match.group(1) if match else None


def _extract_branch(accession: str) -> str | None:
    for prefix, branch in BRANCH_MAP.items():
        if accession.startswith(prefix + "_"):
            return branch
    return None


def _extract_sort_order(accession: str) -> int:
    match = re.search(r"_(\d+)$", accession)
    return int(match.group(1)) if match else 0


def _text(el) -> str:
    """Safely get stripped text from an element."""
    if el is None:
        return ""
    return (el.text or "").strip()


class Command(BaseCommand):
    help = "Download and upsert EDAM ontology terms (OWL/RDF-XML format) into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=None,
            help=(
                f"URL or local file path for EDAM OWL file. "
                f"Defaults to EDAM_OWL_URL env var or {DEFAULT_EDAM_URL}"
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
        from apps.edam.models import EdamTerm

        url = options["url"] or DEFAULT_EDAM_URL
        branch_filter = options["branch"]
        dry_run = options["dry_run"]

        # ----------------------------------------------------------------
        # Step 1: Load OWL/RDF-XML
        # ----------------------------------------------------------------
        self.stdout.write(f"Loading EDAM from: {url}")
        try:
            if url.startswith("http"):
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "denbi-registry/1.0 sync_edam"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw_bytes = resp.read()
            else:
                with open(url, "rb") as f:
                    raw_bytes = f.read()
        except Exception as e:
            raise CommandError(f"Failed to load EDAM: {e}")

        self.stdout.write(f"Downloaded {len(raw_bytes):,} bytes. Parsing OWL/RDF-XML...")

        # ----------------------------------------------------------------
        # Step 2: Parse RDF/XML
        # ----------------------------------------------------------------
        try:
            root = ET.fromstring(raw_bytes)
        except ET.ParseError as e:
            raise CommandError(f"Failed to parse OWL XML: {e}")

        # Extract ontology version from owl:Ontology element
        edam_version = ""
        ontology_el = root.find(_tag(OWL, "Ontology"))
        if ontology_el is not None:
            version_el = ontology_el.find(_tag(OWL, "versionInfo"))
            if version_el is None:
                version_el = ontology_el.find(f"{{{RDFS}}}comment")
            edam_version = _text(version_el)
            # Also check rdf:about attribute for version IRI
            if not edam_version:
                version_iri = ontology_el.get(_tag(RDF, "about"), "")
                m = re.search(r"(\d+\.\d+)", version_iri)
                if m:
                    edam_version = m.group(1)

        self.stdout.write(f"EDAM version: {edam_version or 'unknown'}")

        # ----------------------------------------------------------------
        # Step 3: Parse owl:Class entries
        # ----------------------------------------------------------------
        terms: dict[str, dict] = {}

        for cls in root.findall(_tag(OWL, "Class")):
            uri = cls.get(_tag(RDF, "about"), "")
            if not uri or EDAM_BASE not in uri:
                continue

            accession = _extract_accession(uri)
            if not accession:
                continue

            branch = _extract_branch(accession)
            if not branch:
                continue

            if branch_filter != "all" and branch != branch_filter:
                continue

            # Label — rdfs:label
            label_el = cls.find(_tag(RDFS, "label"))
            label = _text(label_el)
            if not label:
                continue  # Skip anonymous/unlabelled classes

            # Definition — oboInOwl:hasDefinition or rdfs:comment
            defn_el = (
                cls.find(_tag(OBOINOWL, "hasDefinition"))
                or cls.find(_tag(RDFS, "comment"))
            )
            definition = _text(defn_el)

            # Synonyms — oboInOwl:hasExactSynonym (multiple elements)
            synonyms = [
                _text(s)
                for s in cls.findall(_tag(OBOINOWL, "hasExactSynonym"))
                if _text(s)
            ]
            # Also pick up hasNarrowSynonym, hasBroadSynonym for search richness
            for syn_tag in ("hasNarrowSynonym", "hasBroadSynonym", "hasRelatedSynonym"):
                synonyms.extend(
                    _text(s)
                    for s in cls.findall(_tag(OBOINOWL, syn_tag))
                    if _text(s)
                )

            # Parent URI — rdfs:subClassOf (take first EDAM parent)
            parent_uri = None
            for sc in cls.findall(_tag(RDFS, "subClassOf")):
                candidate = sc.get(_tag(RDF, "resource"), "")
                if candidate and EDAM_BASE in candidate and _extract_accession(candidate):
                    parent_uri = candidate
                    break

            # Obsolete flag — owl:deprecated
            deprecated_el = cls.find(_tag(OWL, "deprecated"))
            is_obsolete = _text(deprecated_el).lower() in ("true", "1") if deprecated_el is not None else False

            terms[uri] = {
                "uri": uri,
                "accession": accession,
                "branch": branch,
                "label": label,
                "definition": definition,
                "synonyms": synonyms,
                "parent_uri": parent_uri,
                "is_obsolete": is_obsolete,
                "sort_order": _extract_sort_order(accession),
                "edam_version": edam_version,
            }

        self.stdout.write(f"Parsed {len(terms)} terms.")

        counts = defaultdict(int)
        for t in terms.values():
            counts[t["branch"]] += 1
        for branch, count in sorted(counts.items()):
            self.stdout.write(f"  {branch}: {count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no database writes."))
            return

        # ----------------------------------------------------------------
        # Step 4: Upsert (without parent FKs first)
        # ----------------------------------------------------------------
        self.stdout.write("Writing to database...")
        created_count = 0
        updated_count = 0

        for uri, data in terms.items():
            obj, created = EdamTerm.objects.update_or_create(
                uri=uri,
                defaults={
                    "accession":    data["accession"],
                    "branch":       data["branch"],
                    "label":        data["label"],
                    "definition":   data["definition"],
                    "synonyms":     data["synonyms"],
                    "is_obsolete":  data["is_obsolete"],
                    "sort_order":   data["sort_order"],
                    "edam_version": data["edam_version"],
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        # ----------------------------------------------------------------
        # Step 5: Second pass — resolve parent FKs
        # ----------------------------------------------------------------
        self.stdout.write("Resolving parent relationships...")
        for uri, data in terms.items():
            parent_uri = data.get("parent_uri")
            if not parent_uri:
                continue
            try:
                parent_obj = EdamTerm.objects.get(uri=parent_uri)
                EdamTerm.objects.filter(uri=uri).update(parent=parent_obj)
            except EdamTerm.DoesNotExist:
                pass

        # ----------------------------------------------------------------
        # Step 6: Mark removed terms as obsolete
        # ----------------------------------------------------------------
        known_uris = set(terms.keys())
        if branch_filter == "all":
            newly_obsolete = EdamTerm.objects.exclude(uri__in=known_uris).exclude(is_obsolete=True)
            obsolete_count = newly_obsolete.update(is_obsolete=True)
            if obsolete_count:
                self.stdout.write(self.style.WARNING(f"Marked {obsolete_count} removed terms as obsolete."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, Updated: {updated_count}, "
                f"Total terms: {EdamTerm.objects.count()}"
            )
        )
