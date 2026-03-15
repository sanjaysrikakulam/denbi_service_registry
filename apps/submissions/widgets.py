"""
Custom Form Widgets
===================
EdamAutocompleteWidget: a searchable multi-select for EDAM ontology terms.

Renders as a standard <select multiple> that is progressively enhanced
by Tom Select (a lightweight Select2 alternative, ~17 KB gzipped) via
the base template.

Why Tom Select instead of plain <select>?
  - 4000 options in a flat <select> are unusable on mobile and slow in browsers
  - Tom Select virtualises the option list and filters by typing
  - It degrades gracefully to a plain <select> if JS is unavailable
  - No jQuery dependency (unlike Select2)

The widget groups options by branch for clarity when the user opens the
full option list without typing.
"""
from django import forms


class EdamAutocompleteWidget(forms.SelectMultiple):
    """
    Searchable multi-select widget for EDAM terms.

    Usage:
        class MyForm(forms.ModelForm):
            class Meta:
                widgets = {
                    "edam_topics": EdamAutocompleteWidget(attrs={"data-max-items": "6"}),
                }

    Attributes:
        data-max-items  : Maximum number of terms the user can select (default: 6)
        data-branch     : EDAM branch to filter (topic, operation, data, format)
                          Set automatically by the form based on the field name.
        data-placeholder: Placeholder text shown when nothing is selected.
    """

    def __init__(self, attrs=None, branch: str = "", placeholder: str = "Search EDAM terms…"):
        default_attrs = {
            "class": "edam-autocomplete",
            "data-branch": branch,
            "data-placeholder": placeholder,
            "data-max-items": "6",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    class Media:
        # Tom Select 2.3.1 — vendored locally in static/ (no CDN dependency)
        css = {
            "all": ["css/tom-select.bootstrap5.min.css"],
        }
        js = [
            "js/tom-select.complete.min.js",
        ]
