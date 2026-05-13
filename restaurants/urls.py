from django.urls import path

from . import views

app_name = "restaurants"

urlpatterns = [
    path("dashboard/", views.DashboardTodayView.as_view(), name="dashboard"),
    path("dashboard/publish-booking/", views.publish_booking_link, name="publish_booking_link"),
    path("dashboard/upcoming/", views.DashboardUpcomingView.as_view(), name="dashboard_upcoming"),
    path("dashboard/booking/<int:pk>/", views.BookingDetailView.as_view(), name="booking_detail"),
    path("dashboard/settings/", views.RestaurantSettingsView.as_view(), name="settings"),
    path("dashboard/tables/add/", views.add_table, name="add_table"),
    path("dashboard/services/add/", views.add_service, name="add_service"),
    path("dashboard/blocked-dates/add/", views.add_closed_date, name="add_closed_date"),
    path("dashboard/booking/<int:pk>/status/<str:status>/", views.update_booking_status, name="booking_status"),
    path("dashboard/billing/portal/", views.billing_portal, name="billing_portal"),
]
