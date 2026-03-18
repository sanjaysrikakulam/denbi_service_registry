"""
API Admin
=========
Custom TokenAdmin that masks auth token keys in the admin interface.

- List view: shows only the first 8 characters followed by "…"
- Change view: key field is hidden (not editable, not displayed)
- Creation: full key shown once in a dismissible banner with a copy button
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from rest_framework.authtoken.admin import TokenAdmin as DefaultTokenAdmin
from rest_framework.authtoken.models import TokenProxy


# ---------------------------------------------------------------------------
# Unregister the default DRF TokenAdmin and replace with our own
# ---------------------------------------------------------------------------

admin.site.unregister(TokenProxy)


def _mask_key(key: str) -> str:
    return f"{key[:8]}…" if key else "—"


@admin.register(TokenProxy)
class TokenAdmin(DefaultTokenAdmin):
    list_display = ("masked_key", "user", "created")

    def masked_key(self, obj):
        """Show only a prefix of the token key."""
        return _mask_key(obj.key)

    masked_key.short_description = "Key (masked)"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Mask the token key in the change view page title."""
        response = super().changeform_view(request, object_id, form_url, extra_context)
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and obj.key:
                if hasattr(response, "render"):
                    response.render()
                response.content = response.content.replace(
                    obj.key.encode(), _mask_key(obj.key).encode()
                )
        return response

    def response_add(self, request, obj, post_url_continue=None):
        """Show the full key exactly once after creation."""
        self.message_user(
            request,
            format_html(
                "<strong>⚠ Token created for {user}.</strong> "
                "This key is shown <strong>once only</strong> — "
                "copy it now before navigating away."
                '<div style="margin:8px 0">'
                '<code id="admin-token-key" style="font-size:14px;'
                "user-select:all;padding:6px 10px;background:#f8f9fa;"
                'border:1px solid #dee2e6;border-radius:4px;display:inline-block">'
                "{key}</code>"
                "</div>"
                '<button type="button" onclick="'
                "navigator.clipboard.writeText("
                "document.getElementById('admin-token-key').textContent"
                ").then(function(){{var b=event.target;b.textContent='✓ Copied';"
                "setTimeout(function(){{b.textContent='Copy to clipboard'}},3000)}}"
                ')" style="cursor:pointer;padding:4px 12px;font-size:13px;'
                "border:1px solid #6c757d;border-radius:4px;background:#fff;"
                'color:#333">Copy to clipboard</button>',
                user=obj.user.username,
                key=obj.key,
            ),
            messages.WARNING,
        )
        return super().response_add(request, obj, post_url_continue)
