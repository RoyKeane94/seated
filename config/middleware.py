import uuid


class RequestIdMiddleware:
    """Attach correlation_id for error pages and downstream logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.correlation_id = uuid.uuid4().hex[:12]
        response = self.get_response(request)
        rid = getattr(request, "correlation_id", "")
        if rid:
            response["X-Request-ID"] = rid
        return response
