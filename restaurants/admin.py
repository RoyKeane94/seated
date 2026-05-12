from django.contrib import admin

from .models import ClosedDate, Restaurant, Service, Table


class TableInline(admin.TabularInline):
    model = Table
    extra = 0


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "plan", "subscription_active", "created_at")
    search_fields = ("name", "slug", "owner__username", "owner__email")
    list_filter = ("plan", "subscription_active")
    inlines = [TableInline, ServiceInline]


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("label", "restaurant", "seats", "is_combinable")
    list_filter = ("is_combinable", "restaurant")
    search_fields = ("label", "restaurant__name")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "sitting_mode", "is_active")
    list_filter = ("sitting_mode", "is_active", "restaurant")
    search_fields = ("name", "restaurant__name")


@admin.register(ClosedDate)
class ClosedDateAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "date", "service", "all_day", "reason")
    list_filter = ("all_day", "restaurant")
    search_fields = ("restaurant__name", "reason")
