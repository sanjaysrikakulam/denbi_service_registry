"""
EDAM Ontology Models
====================
Stores the EDAM bioscientific data analysis ontology locally so that:
  - The form can offer a fast, searchable multi-select without network calls
  - EDAM terms linked to submissions are stable even if the ontology updates
  - The API can expose EDAM associations in a machine-readable, URI-anchored way

EDAM structure
--------------
EDAM has five top-level branches, each with a namespace prefix:

  topic_*       Scientific topic / domain  (e.g. Proteomics, Genomics)
  operation_*   Computational operation    (e.g. Sequence alignment, Visualisation)
  data_*        Type of data               (e.g. Sequence record, Phylogenetic tree)
  format_*      Data format                (e.g. FASTA, BAM, JSON)
  identifier_*  Data identifier            (e.g. UniProt accession, DOI)

For a service registration form, Topic and Operation are the most relevant
branches. Data and Format are useful for detailed tool descriptions.

Seeding
-------
EDAM is published as JSON-LD at:
  https://edamontology.org/EDAM.json

The management command `manage.py sync_edam` downloads this file, parses it,
and upserts all terms into this table. Run it once on initial deployment and
again when a new EDAM release is published.

See: https://edamontology.org/  and  https://github.com/edamontology/edamontology
"""

from django.db import models


class EdamBranch(models.TextChoices):
    TOPIC = "topic", "Topic"
    OPERATION = "operation", "Operation"
    DATA = "data", "Data"
    FORMAT = "format", "Format"
    IDENTIFIER = "identifier", "Identifier"


class EdamTerm(models.Model):
    """
    A single term from the EDAM ontology.

    The ``uri`` is the canonical, globally unique identifier
    (e.g. ``http://edamontology.org/topic_0091``).
    The ``accession`` is the short form (e.g. ``topic_0091``).

    Parent–child relationships are stored via the ``parent`` self-FK
    so that hierarchical filtering (e.g. "show only direct children of
    'Sequence analysis'") is possible without parsing URIs.
    """

    # Canonical identifier — used in API responses for machine consumers
    uri = models.URLField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Full EDAM URI, e.g. http://edamontology.org/topic_0091.",
    )
    # Short form — used for display and filtering
    accession = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        help_text="Short EDAM accession, e.g. topic_0091.",
    )
    branch = models.CharField(
        max_length=20,
        choices=EdamBranch.choices,
        db_index=True,
        help_text="Top-level EDAM branch this term belongs to.",
    )
    label = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Human-readable preferred label, e.g. 'Proteomics'.",
    )
    definition = models.TextField(
        blank=True,
        help_text="EDAM definition text for this term.",
    )
    synonyms = models.JSONField(
        default=list,
        help_text="List of synonym strings for search augmentation.",
    )
    # Parent term for hierarchical display in the form
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        help_text="Direct parent term in the EDAM hierarchy.",
    )
    is_obsolete = models.BooleanField(
        default=False,
        help_text="Obsolete terms are hidden from form dropdowns but retained for historical records.",
    )
    # Numeric part of the accession for fast ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Numeric part of the accession; used for stable ordering within a branch.",
    )
    # Track when we last pulled this from the ontology
    edam_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="EDAM release version this term was last updated from, e.g. '1.25'.",
    )

    class Meta:
        verbose_name = "EDAM Term"
        verbose_name_plural = "EDAM Terms"
        ordering = ["branch", "sort_order"]
        indexes = [
            models.Index(fields=["branch", "is_obsolete"]),
            models.Index(fields=["label"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.accession})"

    @property
    def short_label(self) -> str:
        """Label suitable for compact display in multi-select widgets."""
        return self.label

    @property
    def url(self) -> str:
        """Canonical EDAM ontology page URL."""
        return f"https://edamontology.org/{self.accession}"
