"""
API Permissions
===============
Custom DRF permission classes enforcing the two-tier access model:

  IsAdminTokenUser   : Requires DRF Token auth (staff/integrations).
  IsSubmissionOwner  : Requires ApiKey auth whose submission matches the URL.
  IsAdminOrOwner     : Allows either — used for detail GET/PATCH.
"""
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAdminTokenUser(BasePermission):
    """
    Grants access when the request carries a DRF Token
    (Authorization: Token <key>) for an active staff user.

    DRF sets request.auth to the Token ORM object on success.
    SubmissionAPIKey auth sets request.user to a ServiceSubmission,
    so the is_staff check naturally returns False for those requests.
    """
    message = "Admin token authentication required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        from rest_framework.authtoken.models import Token
        return (
            isinstance(request.auth, Token)
            and bool(request.user and request.user.is_active and request.user.is_staff)
        )


class IsSubmissionOwner(BasePermission):
    """
    Allow access when the request is authenticated with a SubmissionAPIKey
    whose submission matches the URL, and whose scope permits the HTTP method.

    Scope rules:
      read  → GET, HEAD, OPTIONS only
      write → GET, HEAD, OPTIONS, PATCH
    """

    message = "You do not have permission to access this submission."

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.submissions.models import ServiceSubmission, SubmissionAPIKey
        if not isinstance(request.user, ServiceSubmission):
            return False
        # Scope check: read-only keys cannot PATCH
        key = request.auth  # SubmissionAPIKey instance set by our auth backend
        if isinstance(key, SubmissionAPIKey):
            if key.scope == SubmissionAPIKey.SCOPE_READ and request.method not in self.SAFE_METHODS:
                self.message = "This API key is read-only. Use a write-scoped key to modify data."
                return False
        return True

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        from apps.submissions.models import ServiceSubmission
        if not isinstance(request.user, ServiceSubmission):
            return False
        return str(request.user.pk) == str(obj.pk)


class IsAdminOrOwner(BasePermission):
    """
    Grants access if either IsAdminTokenUser or IsSubmissionOwner passes.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        admin_perm = IsAdminTokenUser()
        owner_perm = IsSubmissionOwner()
        return (
            admin_perm.has_permission(request, view)
            or owner_perm.has_permission(request, view)
        )

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        admin_perm = IsAdminTokenUser()
        owner_perm = IsSubmissionOwner()
        return (
            admin_perm.has_permission(request, view)
            or owner_perm.has_object_permission(request, view, obj)
        )
