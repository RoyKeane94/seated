from django.conf import settings


def seated_globals(request):
    return {
        "correlation_id": getattr(request, "correlation_id", "") or None,
        "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        "embedded": request.GET.get("embedded") == "true",
    }
