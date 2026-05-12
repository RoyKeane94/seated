import logging
import sys

from django.apps import AppConfig
from django.core.signals import got_request_exception


def _log_request_exception(_sender, **kwargs):
    request = kwargs.get("request")
    exc_type, exc_value, traceback = sys.exc_info()
    if exc_type is None:
        return
    logger = logging.getLogger("seated.request")
    path = getattr(request, "path", "-")
    method = getattr(request, "method", "-")
    cid = getattr(request, "correlation_id", None) or "-"
    logger.error(
        "Unhandled exception during request path=%s method=%s correlation_id=%s",
        path,
        method,
        cid,
        exc_info=(exc_type, exc_value, traceback),
        extra={
            "request_path": path,
            "request_method": method,
            "correlation_id": cid,
        },
    )


class ConfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "config"

    def ready(self):
        got_request_exception.connect(_log_request_exception, weak=False, dispatch_uid="seated_request_exception_logging")
