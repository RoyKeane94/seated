from django.contrib import admin

from .models import Booking, EmailLog


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "guest_name", "party_size", "date", "time", "status", "source")
    list_filter = ("status", "source", "restaurant")
    search_fields = ("guest_name", "guest_email", "restaurant__name")
    date_hierarchy = "date"


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("kind", "to_email", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("to_email", "subject")
