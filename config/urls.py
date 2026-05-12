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
