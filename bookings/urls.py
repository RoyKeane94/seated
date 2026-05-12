from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("book/<slug:slug>/", views.booking_page, name="booking_page"),
    path("book/<slug:slug>/success/<int:booking_id>/", views.booking_success, name="booking_success"),
    path("bookings/<int:booking_id>/calendar.ics", views.booking_ics, name="booking_ics"),
    path("booking/cancel/<uuid:cancel_token>/", views.booking_cancel, name="booking_cancel"),
    path("booking/modify/<uuid:modify_token>/", views.booking_modify, name="booking_modify"),
    path("api/widget/<slug:slug>/", views.widget_api, name="widget_api"),
    path("api/book/<slug:slug>/", views.booking_api, name="booking_api"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
