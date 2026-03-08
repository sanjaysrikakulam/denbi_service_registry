"""
Health Check URLs and Views
============================
Two endpoints used by Docker health checks and load balancers:

  GET /health/live/   — Returns 200 if the Django process is alive.
                        Does not check DB or Redis. Used by Docker HEALTHCHECK.

  GET /health/ready/  — Returns 200 only if DB and Redis are reachable.
                        Used by orchestrators before routing traffic.
"""
import logging

from django.db import connection, OperationalError
from django.http import JsonResponse
from django.urls import path

logger = logging.getLogger(__name__)


def liveness(request):
    """Process is alive — no external dependency checks."""
    return JsonResponse({"status": "ok"})


def readiness(request):
    """Check DB and Redis connectivity before declaring ready."""
    checks = {}

    # Database check
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except OperationalError as e:
        logger.error(f"Readiness: database check failed: {e}")
        checks["database"] = "error"

    # Redis check
    try:
        from django.core.cache import cache
        cache.set("_health_check", "1", timeout=5)
        val = cache.get("_health_check")
        checks["redis"] = "ok" if val == "1" else "error"
    except Exception as e:
        logger.error(f"Readiness: Redis check failed: {e}")
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    status = 200 if all_ok else 503

    return JsonResponse({"status": "ok" if all_ok else "degraded", "checks": checks}, status=status)


urlpatterns = [
    path("live/", liveness, name="health-live"),
    path("ready/", readiness, name="health-ready"),
]
