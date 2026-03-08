from django.contrib import admin
from .models import EdamTerm


@admin.register(EdamTerm)
class EdamTermAdmin(admin.ModelAdmin):
    list_display = ("accession", "label", "branch", "is_obsolete", "edam_version")
    list_filter = ("branch", "is_obsolete")
    search_fields = ("accession", "label", "definition")
    readonly_fields = ("uri", "accession", "branch", "sort_order", "edam_version", "parent")
    ordering = ("branch", "sort_order")

    def has_add_permission(self, request):
        return False  # All terms come from sync_edam command

    def has_delete_permission(self, request, obj=None):
        return False  # Delete via sync_edam --prune only
