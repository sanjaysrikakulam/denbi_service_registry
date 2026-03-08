"""
API Views
=========
DRF ViewSets for the de.NBI Service Registry REST API.

Authentication strategy
-----------------------
- POST /submissions/           — public, no auth needed
- GET  /submissions/           — admin Token auth (list all)
- GET  /submissions/{id}/      — ApiKey auth (owner sees own record)
- PATCH /submissions/{id}/     — ApiKey auth (owner updates own record)

`get_authenticators` is called *during* request initialisation before
`self.action` is set, so we inspect `self.request.method` and
`self.kwargs` (router-populated) instead.
"""
import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import filters, mixins, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from apps.registry.models import PrincipalInvestigator, ServiceCategory, ServiceCenter
from apps.submissions.models import ServiceSubmission, SubmissionAPIKey
from apps.submissions.tasks import send_submission_notification

from .authentication import SubmissionAPIKeyAuthentication
from .permissions import IsAdminOrOwner, IsAdminTokenUser, IsSubmissionOwner
from .serializers import (
    PrincipalInvestigatorSerializer,
    ServiceCategorySerializer,
    ServiceCenterSerializer,
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_detail_action(view):
    """
    Return True when the request targets a specific object (has a pk/uuid
    in the URL kwargs). Works before self.action is populated.
    """
    return bool(view.kwargs.get(view.lookup_field) or view.kwargs.get("pk"))


# ---------------------------------------------------------------------------
# SubmissionViewSet
# ---------------------------------------------------------------------------

@extend_schema(tags=["Submissions"])
class SubmissionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Service submission resource.

    | Method | URL | Auth | Description |
    |--------|-----|------|-------------|
    | POST | /api/v1/submissions/ | None | Register a new service |
    | GET | /api/v1/submissions/ | Admin Token | List all submissions |
    | GET | /api/v1/submissions/{id}/ | ApiKey | Retrieve your submission |
    | PATCH | /api/v1/submissions/{id}/ | ApiKey | Update your submission |

    **One-time API key:** A `POST` response includes a plaintext `api_key`.
    Store it immediately — it is shown exactly once and never stored.

    Use it in subsequent requests as:
    ```
    Authorization: ApiKey <your-key>
    ```
    """

    queryset = ServiceSubmission.objects.select_related(
        "service_center"
    ).prefetch_related(
        "service_categories", "responsible_pis"
    ).order_by("-submitted_at")

    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["submitted_at", "updated_at", "service_name"]

    # ── Auth / permission — safe to call before self.action is set ───────────

    def get_authenticators(self):
        """
        Called during request initialisation before self.action exists.
        Use method + URL kwargs to decide auth scheme.
        - POST (create) → no authentication required
        - GET list      → admin Token
        - GET/PATCH detail → ApiKey (owner) or Token (admin)
        """
        method = getattr(self, "request", None)
        http_method = (self.request.method if hasattr(self, "request") and self.request else "GET")

        # Creation is open — no auth needed
        if http_method == "POST" and not _is_detail_action(self):
            return []

        # All other requests accept both schemes; permissions filter further
        return [TokenAuthentication(), SubmissionAPIKeyAuthentication()]

    def get_permissions(self):
        """
        Called after get_authenticators; self.action *may* still not be set
        on some Django/DRF paths, so guard with getattr.
        """
        action = getattr(self, "action", None)
        method = getattr(self.request, "method", "GET") if hasattr(self, "request") else "GET"

        if action == "create" or (method == "POST" and not _is_detail_action(self)):
            return [AllowAny()]
        if action == "list" or (method == "GET" and not _is_detail_action(self)):
            return [IsAdminTokenUser()]
        return [IsAdminOrOwner()]

    # ── Serializer selection ─────────────────────────────────────────────────

    def get_serializer_class(self):
        action = getattr(self, "action", None)
        if action == "create":
            return SubmissionCreateSerializer
        if action == "list":
            return SubmissionListSerializer
        return SubmissionDetailSerializer

    # ── Queryset scoping ─────────────────────────────────────────────────────

    def get_queryset(self):
        qs = super().get_queryset()

        # ApiKey authentication sets request.user to the ServiceSubmission object
        if isinstance(self.request.user, ServiceSubmission):
            return qs.filter(id=self.request.user.id)

        # Admin token: support optional query-param filters
        params = self.request.query_params

        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        center = params.get("service_center")
        if center:
            qs = qs.filter(service_center__short_name__icontains=center)

        year = params.get("year_established")
        if year and year.isdigit():
            qs = qs.filter(year_established=int(year))

        elixir = params.get("register_as_elixir")
        if elixir in ("true", "1"):
            qs = qs.filter(register_as_elixir=True)
        elif elixir in ("false", "0"):
            qs = qs.filter(register_as_elixir=False)

        return qs

    # ── Actions ──────────────────────────────────────────────────────────────

    @extend_schema(
        summary="Register a new de.NBI service",
        description=(
            "Submit a new service registration. No authentication required.\n\n"
            "**Important:** The response includes a one-time `api_key` field. "
            "This key is shown exactly once — save it immediately. "
            "You will need it to retrieve or update your submission.\n\n"
            "Use it in subsequent requests as:\n"
            "```\nAuthorization: ApiKey <your-key>\n```"
        ),
        responses={201: SubmissionCreateSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission = serializer.save(
            status="submitted",
            submission_ip=self._get_client_ip(request),
        )

        _, plaintext = SubmissionAPIKey.create_for_submission(
            submission=submission,
            label="Initial key",
            created_by="submitter",
        )

        logger.info(
            "API submission created",
            extra={"submission_id": str(submission.id)},
        )

        send_submission_notification.delay(str(submission.id), event="created")

        output = SubmissionCreateSerializer(
            submission,
            context={"request": request, "api_key_plaintext": plaintext},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Retrieve your submission",
        description=(
            "Returns the full submission data for the submission linked to your API key.\n\n"
            "Requires `Authorization: ApiKey <your-key>` header."
        ),
        responses={200: SubmissionDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="List all submissions",
        description=(
            "Returns a paginated list of all service submissions.\n\n"
            "Requires admin `Authorization: Token <admin-token>` header.\n\n"
            "**Filters:**\n"
            "- `?status=submitted|under_review|approved|rejected`\n"
            "- `?service_center=<short_name>`\n"
            "- `?year_established=<year>`\n"
            "- `?register_as_elixir=true|false`\n"
            "- `?ordering=submitted_at|updated_at|service_name` (prefix `-` for descending)"
        ),
        parameters=[
            OpenApiParameter("status", str, description="Filter by status"),
            OpenApiParameter("service_center", str, description="Filter by service centre short name"),
            OpenApiParameter("year_established", int, description="Filter by year established"),
            OpenApiParameter("register_as_elixir", str, description="Filter by ELIXIR registration (true/false)"),
        ],
        responses={200: SubmissionListSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Update your submission (partial)",
        description=(
            "Partial update — include only the fields you want to change.\n\n"
            "Requires `Authorization: ApiKey <your-key>` header.\n\n"
            "Note: updating an approved submission resets its status to `submitted` "
            "for re-review."
        ),
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if instance.status == "approved":
            instance.status = "submitted"
            instance.save(update_fields=["status"])

        send_submission_notification.delay(str(instance.id), event="updated")
        logger.info("API submission updated", extra={"submission_id": str(instance.id)})
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Full PUT is disabled — use PATCH."""
        if not kwargs.get("partial"):
            return Response(
                {"detail": "Full replacement (PUT) is not supported. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    @staticmethod
    def _get_client_ip(request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


# ---------------------------------------------------------------------------
# Reference data viewsets (admin-only, read-only)
# ---------------------------------------------------------------------------

@extend_schema(tags=["Reference Data"])
class ServiceCategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List active service categories. Requires admin token."""
    queryset = ServiceCategory.objects.filter(is_active=True)
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAdminTokenUser]
    authentication_classes = [TokenAuthentication]
    pagination_class = None


@extend_schema(tags=["Reference Data"])
class ServiceCenterViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List active de.NBI service centres. Requires admin token."""
    queryset = ServiceCenter.objects.filter(is_active=True)
    serializer_class = ServiceCenterSerializer
    permission_classes = [IsAdminTokenUser]
    authentication_classes = [TokenAuthentication]
    pagination_class = None


@extend_schema(tags=["Reference Data"])
class PrincipalInvestigatorViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List active PIs in the de.NBI network. Requires admin token."""
    queryset = PrincipalInvestigator.objects.filter(is_active=True).order_by("last_name")
    serializer_class = PrincipalInvestigatorSerializer
    permission_classes = [IsAdminTokenUser]
    authentication_classes = [TokenAuthentication]
    pagination_class = None


# ---------------------------------------------------------------------------
# EDAM ViewSet
# ---------------------------------------------------------------------------

@extend_schema(tags=["EDAM Ontology"])
class EdamTermViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    EDAM ontology terms — public, no authentication required.

    **Filters:**
    - `?branch=topic|operation|data|format`
    - `?q=<search term>` — searches label and definition
    """
    from apps.edam.models import EdamTerm
    from apps.api.serializers import EdamTermSerializer, EdamTermDetailSerializer

    queryset = EdamTerm.objects.filter(is_obsolete=False).select_related("parent")
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None

    def get_serializer_class(self):
        from apps.api.serializers import EdamTermSerializer, EdamTermDetailSerializer
        if getattr(self, "action", None) == "retrieve":
            return EdamTermDetailSerializer
        return EdamTermSerializer

    def get_queryset(self):
        from apps.edam.models import EdamTerm
        from django.db.models import Q
        qs = EdamTerm.objects.filter(is_obsolete=False).select_related("parent")
        branch = self.request.query_params.get("branch")
        if branch:
            qs = qs.filter(branch=branch)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(label__icontains=q) | Q(definition__icontains=q))
        return qs.order_by("branch", "sort_order")

    def get_object(self):
        from apps.edam.models import EdamTerm
        lookup = self.kwargs.get(self.lookup_field)
        try:
            return EdamTerm.objects.get(accession=lookup)
        except EdamTerm.DoesNotExist:
            return super().get_object()


# ---------------------------------------------------------------------------
# bio.tools ViewSet
# ---------------------------------------------------------------------------

@extend_schema(tags=["bio.tools Integration"])
class BioToolsRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    bio.tools integration records — locally cached snapshots linked to
    de.NBI service registrations, refreshed daily by a Celery task.

    - List: requires admin token.
    - Retrieve (by biotoolsID): public for approved submissions.

    **Filters:** `?submission=<uuid>`, `?biotools_id=<id>`
    """
    from apps.api.serializers import BioToolsRecordSerializer
    serializer_class = BioToolsRecordSerializer

    def get_queryset(self):
        from apps.biotools.models import BioToolsRecord
        qs = BioToolsRecord.objects.select_related("submission").prefetch_related("functions")
        biotools_id = self.request.query_params.get("biotools_id")
        if biotools_id:
            qs = qs.filter(biotools_id=biotools_id)
        submission_id = self.request.query_params.get("submission")
        if submission_id:
            qs = qs.filter(submission_id=submission_id)
        return qs

    def get_permissions(self):
        if getattr(self, "action", None) == "retrieve":
            return [AllowAny()]
        return [IsAdminTokenUser()]

    def get_authenticators(self):
        return [TokenAuthentication(), SubmissionAPIKeyAuthentication()]

    def get_object(self):
        from apps.biotools.models import BioToolsRecord
        lookup = self.kwargs.get(self.lookup_field)
        try:
            return BioToolsRecord.objects.select_related("submission").prefetch_related("functions").get(
                biotools_id=lookup
            )
        except BioToolsRecord.DoesNotExist:
            return super().get_object()
