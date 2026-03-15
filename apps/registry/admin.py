"""
Registry Admin
==============
Provides Django admin interfaces for the reference data models:
ServiceCategory, ServiceCenter, PrincipalInvestigator.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import PrincipalInvestigator, ServiceCategory, ServiceCenter


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    """Admin for service category lookup table."""

    list_display = ("name", "is_active")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(ServiceCenter)
class ServiceCenterAdmin(admin.ModelAdmin):
    """Admin for de.NBI service centres."""

    list_display = ("short_name", "full_name", "website_link", "is_active")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("short_name", "full_name")
    ordering = ("full_name",)
    readonly_fields = ("id",)

    fieldsets = (
        (
            None,
            {
                "fields": ("id", "short_name", "full_name", "website", "is_active"),
            },
        ),
    )

    @admin.display(description="Website")
    def website_link(self, obj):
        if obj.website:
            return format_html(
                '<a href="{}" target="_blank">{}</a>', obj.website, obj.website
            )
        return "—"


@admin.register(PrincipalInvestigator)
class PrincipalInvestigatorAdmin(admin.ModelAdmin):
    """Admin for named PIs in the de.NBI network."""

    list_display = (
        "last_name",
        "first_name",
        "institute",
        "orcid_link",
        "is_active",
        "is_associated_partner",
    )
    list_editable = ("is_active",)
    list_filter = ("is_active", "is_associated_partner", "institute")
    search_fields = ("last_name", "first_name", "email", "institute")
    ordering = ("last_name", "first_name")
    readonly_fields = ("id",)

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("id", "last_name", "first_name", "orcid"),
            },
        ),
        (
            "Affiliation",
            {
                "fields": ("institute", "email"),
            },
        ),
        (
            "Status",
            {
                "fields": ("is_active", "is_associated_partner"),
                "description": (
                    "Set is_active=False to hide this PI from the form without "
                    "removing existing submission links. "
                    "is_associated_partner should be True for only one entry."
                ),
            },
        ),
    )

    @admin.display(description="ORCID")
    def orcid_link(self, obj):
        if obj.orcid:
            url = f"https://orcid.org/{obj.orcid}"
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.orcid)
        return "—"
