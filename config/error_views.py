import logging

from django.shortcuts import render
from django.views.decorators.cache import never_cache

logger = logging.getLogger("seated.errors")


def _ref(request):
    return getattr(request, "correlation_id", None) or "-"


@never_cache
def handler400(request, exception):
    cid = _ref(request)
    logger.warning("400 Bad Request path=%s correlation_id=%s", getattr(request, "path", "-"), cid)
    return render(request, "errors/400.html", status=400)


@never_cache
def handler403(request, exception):
    cid = _ref(request)
    logger.warning("403 Forbidden path=%s correlation_id=%s", getattr(request, "path", "-"), cid)
    return render(request, "errors/403.html", status=403)


@never_cache
def handler404(request, exception):
    cid = _ref(request)
    logger.warning("404 Not Found path=%s correlation_id=%s", getattr(request, "path", "-"), cid)
    return render(request, "errors/404.html", status=404)


@never_cache
def handler500(request):
    cid = _ref(request)
    # Full traceback emitted by got_request_exception (seated.request) when the exception originates in the request cycle.
    logger.error("500 rendering error page path=%s correlation_id=%s", getattr(request, "path", "-"), cid)
    return render(request, "500.html", status=500)
