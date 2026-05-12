from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
from django.urls import include, path


def home(request):
    return render(request, "home.html")


def health(request):
    return HttpResponse("ok")


def favicon(request):
    """Serve raster favicon at /favicon.ico (Chrome reliably uses PNG; extension is legacy)."""
    path = Path(settings.BASE_DIR) / "static/img/favicon.png"
    if not path.is_file():
        return HttpResponse(status=404)
    response = FileResponse(path.open("rb"), content_type="image/png")
    response["Cache-Control"] = "public, max-age=604800, immutable"
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon, name="favicon"),
    path("", home, name="home"),
    path("health/", health, name="health"),
    path("", include("accounts.urls")),
    path("", include("restaurants.urls")),
    path("", include("bookings.urls")),
]

handler400 = "config.error_views.handler400"
handler403 = "config.error_views.handler403"
handler404 = "config.error_views.handler404"
handler500 = "config.error_views.handler500"
