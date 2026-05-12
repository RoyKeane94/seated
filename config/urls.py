from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import include, path


def home(request):
    return render(request, "home.html")


def health(request):
    return HttpResponse("ok")


def favicon_redirect(request):
    """Serve /favicon.ico — browsers prefetch this URL before parsing <link rel=icon>."""
    url = staticfiles_storage.url("img/favicon.svg")
    return HttpResponseRedirect(url)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon_redirect, name="favicon"),
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
