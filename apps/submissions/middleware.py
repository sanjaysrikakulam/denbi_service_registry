"""
Custom Middleware
================
RequestIDMiddleware: Injects a UUID per request, included in all log records
and error responses so support staff can correlate logs to issues.
"""
import uuid
import logging


class RequestIDMiddleware:
    """
    Injects a unique request_id UUID into each request and the log record factory.
    The request_id is included in JSON log output via the logging configuration.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        # Make request_id available to all logging calls in this thread
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request.request_id
            return record

        logging.setLogRecordFactory(record_factory)
        response = self.get_response(request)
        # Echo the request ID in the response for client-side correlation
        response["X-Request-ID"] = request.request_id
        return response
