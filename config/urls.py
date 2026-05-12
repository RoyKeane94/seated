from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path


def home(request):
    return render(request, "home.html")


def health(request):
    return HttpResponse("ok")


urlpatterns = [
    path("admin/", admin.site.urls),
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
