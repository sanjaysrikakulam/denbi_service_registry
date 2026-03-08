"""Custom DRF exception handler — adds request_id to error responses."""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        request = context.get("request")
        request_id = getattr(request, "request_id", None) if request else None

        # Wrap error in a consistent envelope
        response.data = {
            "error": response.data,
            "request_id": request_id,
        }

        if response.status_code >= 500:
            logger.error(
                f"API 5xx error: {exc}",
                extra={"request_id": request_id},
                exc_info=True,
            )

    return response
