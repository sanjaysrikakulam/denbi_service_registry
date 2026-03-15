"""
bio.tools Integration Models
============================

Two models handle everything:

BioToolsRecord
--------------
A locally cached snapshot of a bio.tools tool entry, linked one-to-one with
a ServiceSubmission. It stores the raw JSON returned by the bio.tools API plus
extracted scalar fields for querying and display. Refreshed on a schedule by
the sync_biotools Celery task.

BioToolsFunction
----------------
bio.tools models a tool's functional annotation as a list of "functions", where
each function has:
  - one or more EDAM Operations  (what the tool does)
  - zero or more EDAM Inputs     (data type + format pairs)
  - zero or more EDAM Outputs    (data type + format pairs)

This maps naturally to a related model so that the API can expose it in a
structured, machine-readable way rather than burying it in a JSON blob.

Data flow
---------

  bio.tools API
       │
       ▼  (Celery task: sync_biotools / management cmd: sync_biotools)
  BioToolsRecord.raw_json       ← full API response stored verbatim
  BioToolsRecord scalar fields  ← extracted for fast query/display
  BioToolsFunction rows         ← one per function block in the API response
       │
       ▼
  ServiceSubmission.biotoolsrecord  (OneToOne reverse relation)
       │
       ▼
  API: GET /api/v1/submissions/{id}/  → nested `biotoolsrecord` object
  API: GET /api/v1/biotools/{biotoolsid}/  → standalone record endpoint

EDAM terms on submissions vs bio.tools
---------------------------------------
There are TWO sources of EDAM annotations:

  1. ServiceSubmission.edam_topics / .edam_operations
     — chosen by the submitter via our form, representing how THEY classify
       their service (may be broader or different from bio.tools)

  2. BioToolsRecord → BioToolsFunction → operations/inputs/outputs (EDAM URIs)
     — sourced directly from bio.tools, updated on sync
     — authoritative for the bio.tools-registered tool

Both are exposed in the API separately and can be diffed by consumers.
"""

import uuid

from django.db import models
from django.utils import timezone


class BioToolsRecord(models.Model):
    """
    A locally cached snapshot of one bio.tools tool entry.

    The ``biotools_id`` is the tool's stable identifier in bio.tools
    (the slug part of https://bio.tools/<biotools_id>).

    ``raw_json`` stores the complete API response so that we never lose
    information even if we don't yet have a model field for it.

    Scalar fields are extracted from raw_json on each sync for fast filtering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to the submission that registered this tool
    submission = models.OneToOneField(
        "submissions.ServiceSubmission",
        on_delete=models.CASCADE,
        related_name="biotoolsrecord",
        help_text="The de.NBI service registration this bio.tools record belongs to.",
    )

    # bio.tools stable identifier — the slug in https://bio.tools/<id>
    biotools_id = models.CharField(
        max_length=200,
        db_index=True,
        help_text="bio.tools tool ID, e.g. 'blast' or 'interproscan'.",
    )

    # -----------------------------------------------------------------------
    # Extracted scalar fields (denormalised from raw_json for query/display)
    # -----------------------------------------------------------------------

    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Tool name as it appears in bio.tools.",
    )
    description = models.TextField(
        blank=True,
        help_text="Tool description from bio.tools.",
    )
    homepage = models.URLField(
        blank=True,
        help_text="Tool homepage URL from bio.tools.",
    )
    version = models.CharField(
        max_length=100,
        blank=True,
        help_text="Latest version string from bio.tools.",
    )
    license = models.CharField(
        max_length=100,
        blank=True,
        help_text="SPDX license identifier from bio.tools.",
    )
    # bio.tools maturity: Emerging | Mature | Legacy
    maturity = models.CharField(max_length=50, blank=True)
    # bio.tools cost: Free | Commercial | ...
    cost = models.CharField(max_length=50, blank=True)

    # Tool types as a JSON list: ["Command-line tool", "Web application", ...]
    tool_type = models.JSONField(
        default=list,
        help_text="List of bio.tools toolType values.",
    )
    # Operating systems as a JSON list
    operating_system = models.JSONField(
        default=list,
        help_text="List of operating system names from bio.tools.",
    )
    # Publication list: [{pmid, doi, pmcid, type, note, metadata}]
    publications = models.JSONField(
        default=list,
        help_text="Publications from bio.tools (list of {pmid, doi, pmcid, type}).",
    )
    # Documentation links: [{url, type}]
    documentation = models.JSONField(
        default=list,
        help_text="Documentation links from bio.tools.",
    )
    # Download links: [{url, type, version}]
    download = models.JSONField(
        default=list,
        help_text="Download links from bio.tools.",
    )
    # Links: [{url, type}]
    links = models.JSONField(
        default=list,
        help_text="Other links from bio.tools.",
    )

    # EDAM topic URIs — extracted for quick API filtering
    # Full structured annotations are in BioToolsFunction
    edam_topic_uris = models.JSONField(
        default=list,
        help_text="List of EDAM topic URIs from bio.tools, e.g. ['http://edamontology.org/topic_0091'].",
    )

    # -----------------------------------------------------------------------
    # Sync metadata
    # -----------------------------------------------------------------------

    raw_json = models.JSONField(
        help_text="Complete raw API response from bio.tools, stored verbatim.",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this record was last refreshed from the bio.tools API.",
    )
    sync_error = models.TextField(
        blank=True,
        help_text="Last sync error message, if any. Empty when last sync succeeded.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "bio.tools Record"
        verbose_name_plural = "bio.tools Records"
        ordering = ["biotools_id"]

    def __str__(self) -> str:
        return f"bio.tools:{self.biotools_id} → {self.submission.service_name}"

    @property
    def biotools_url(self) -> str:
        return f"https://bio.tools/{self.biotools_id}"

    @property
    def sync_ok(self) -> bool:
        return not self.sync_error and self.last_synced_at is not None

    def mark_sync_error(self, error: str) -> None:
        self.sync_error = str(error)[:2000]
        self.save(update_fields=["sync_error", "updated_at"])

    def mark_sync_success(self) -> None:
        self.sync_error = ""
        self.last_synced_at = timezone.now()
        self.save(update_fields=["sync_error", "last_synced_at", "updated_at"])


class BioToolsFunction(models.Model):
    """
    One functional annotation block from bio.tools.

    bio.tools models tool functionality as a list of function objects,
    each describing one mode of operation. A tool may have multiple
    functions (e.g. alignment AND visualisation).

    Each function has:
      - operations : list of EDAM Operation terms (what it does)
      - inputs     : list of {data: EDAM Data URI, format: [EDAM Format URI, ...]}
      - outputs    : list of {data: EDAM Data URI, format: [EDAM Format URI, ...]}
      - cmd        : optional command-line note
      - note       : optional free-text note

    We store the structured data from bio.tools as JSON arrays on this model
    so it is fully machine-readable without the consumer needing to parse
    raw_json themselves.
    """

    record = models.ForeignKey(
        BioToolsRecord,
        on_delete=models.CASCADE,
        related_name="functions",
        help_text="The bio.tools record this function block belongs to.",
    )
    # Position of this function in the bio.tools function list (0-indexed)
    position = models.PositiveSmallIntegerField(default=0)

    # EDAM Operations — list of {uri, term}
    # e.g. [{"uri": "http://edamontology.org/operation_0004", "term": "Operation"}]
    operations = models.JSONField(
        default=list,
        help_text="EDAM Operation annotations: [{uri, term}, ...].",
    )
    # Inputs — list of {data: {uri, term}, formats: [{uri, term}, ...]}
    inputs = models.JSONField(
        default=list,
        help_text="Input data/format annotations from bio.tools.",
    )
    # Outputs — list of {data: {uri, term}, formats: [{uri, term}, ...]}
    outputs = models.JSONField(
        default=list,
        help_text="Output data/format annotations from bio.tools.",
    )
    cmd = models.TextField(
        blank=True,
        help_text="Command-line note from bio.tools (if any).",
    )
    note = models.TextField(
        blank=True,
        help_text="Free-text note for this function from bio.tools.",
    )

    class Meta:
        verbose_name = "bio.tools Function"
        verbose_name_plural = "bio.tools Functions"
        ordering = ["record", "position"]
        unique_together = [("record", "position")]

    def __str__(self) -> str:
        ops = ", ".join(o.get("term", "") for o in self.operations[:2])
        return f"{self.record.biotools_id} / function {self.position}: {ops or '(no operations)'}"
