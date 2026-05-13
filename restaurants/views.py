from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views.generic import DetailView, TemplateView, UpdateView

from bookings.services import invalidate_slots_cache
from bookings.models import Booking
from restaurants.forms import BookingDashboardForm, ClosedDateForm, RestaurantForm, ServiceForm, TableForm
from restaurants.models import ClosedDate, Restaurant, Service, Table

stripe.api_key = settings.STRIPE_SECRET_KEY


class OwnerRequiredMixin(LoginRequiredMixin):
    def get_restaurant(self):
        return get_object_or_404(Restaurant, owner=self.request.user)


class DashboardTodayView(OwnerRequiredMixin, TemplateView):
    template_name = "restaurants/dashboard_today.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        today = timezone.localdate()
        bookings = (
            Booking.objects.filter(restaurant=restaurant, date=today)
            .select_related("table", "service")
            .prefetch_related("combined_tables")
            .order_by("time")
        )
        services = Service.objects.filter(restaurant=restaurant, is_active=True)
        summaries = []
        for service in services:
            service_bookings = [b for b in bookings if b.service_id == service.id and b.status == Booking.STATUS_CONFIRMED]
            booked = sum(b.party_size for b in service_bookings)
            capacity = sum(t.seats for t in restaurant.tables.all())
            summaries.append({"service": service, "booked": booked, "capacity": capacity, "remaining": max(capacity - booked, 0)})
        context.update({"restaurant": restaurant, "today": today, "bookings": bookings, "summaries": summaries})
        return context


class DashboardUpcomingView(OwnerRequiredMixin, TemplateView):
    template_name = "restaurants/dashboard_upcoming.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        start = timezone.localdate()
        end = start + timedelta(days=14)
        grouped = {}
        bookings = (
            Booking.objects.filter(restaurant=restaurant, date__range=(start, end))
            .select_related("table", "service")
            .prefetch_related("combined_tables")
            .order_by("date", "time")
        )
        for booking in bookings:
            grouped.setdefault(booking.date, []).append(booking)
        context.update({"restaurant": restaurant, "grouped_bookings": grouped})
        return context


class BookingDetailView(OwnerRequiredMixin, DetailView):
    model = Booking
    template_name = "restaurants/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.filter(restaurant=self.get_restaurant()).select_related("table", "service")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = BookingDashboardForm(instance=self.object, restaurant=self.get_restaurant())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = BookingDashboardForm(request.POST, instance=self.object, restaurant=self.get_restaurant())
        if form.is_valid():
            updated = form.save()
            updated.combined_tables.set(form.cleaned_data["combined_tables"])
            invalidate_slots_cache(updated.restaurant.slug)
            messages.success(request, "Booking updated.")
            return redirect("restaurants:booking_detail", pk=updated.pk)
        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class RestaurantSettingsView(OwnerRequiredMixin, UpdateView):
    model = Restaurant
    form_class = RestaurantForm
    template_name = "restaurants/settings.html"
    context_object_name = "restaurant"
    success_url = reverse_lazy("restaurants:settings")

    def get_object(self, queryset=None):
        return self.get_restaurant()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        context["table_form"] = TableForm()
        context["service_form"] = ServiceForm()
        context["closed_date_form"] = ClosedDateForm()
        context["tables"] = restaurant.tables.all()
        context["services"] = restaurant.services.all()
        context["closed_dates"] = restaurant.closed_dates.select_related("service")
        context["billing_portal_enabled"] = bool(settings.STRIPE_SECRET_KEY and restaurant.stripe_customer_id)
        return context


@login_required
@require_POST
def add_table(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    form = TableForm(request.POST)
    if form.is_valid():
        table = form.save(commit=False)
        table.restaurant = restaurant
        table.save()
        form.save_m2m()
        messages.success(request, "Table added.")
    return redirect("restaurants:settings")


@login_required
@require_POST
def add_service(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    form = ServiceForm(request.POST)
    if form.is_valid():
        service = form.save(commit=False)
        service.restaurant = restaurant
        service.save()
        messages.success(request, "Service added.")
    return redirect("restaurants:settings")


@login_required
@require_POST
def add_closed_date(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    form = ClosedDateForm(request.POST)
    if form.is_valid():
        closed_date = form.save(commit=False)
        closed_date.restaurant = restaurant
        closed_date.save()
        invalidate_slots_cache(restaurant.slug)
        messages.success(request, "Date blocked.")
    return redirect("restaurants:settings")


@login_required
@require_POST
def update_booking_status(request, pk, status):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    booking = get_object_or_404(Booking, pk=pk, restaurant=restaurant)
    allowed = {
        "no_show": Booking.STATUS_NO_SHOW,
        "cancel": Booking.STATUS_CANCELLED,
        "complete": Booking.STATUS_COMPLETED,
        "confirm": Booking.STATUS_CONFIRMED,
    }
    if status in allowed:
        booking.status = allowed[status]
        booking.save(update_fields=["status", "updated_at"])
        invalidate_slots_cache(restaurant.slug)
    return redirect("restaurants:dashboard")


@login_required
@require_POST
def publish_booking_link(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    restaurant.booking_link_published = True
    restaurant.save(update_fields=["booking_link_published"])
    invalidate_slots_cache(restaurant.slug)
    messages.success(request, "Your booking link is live — guests can book online.")
    return redirect("restaurants:dashboard")


@login_required
def billing_portal(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    if not settings.STRIPE_SECRET_KEY or not restaurant.stripe_customer_id:
        messages.error(request, "Billing portal unavailable.")
        return redirect("restaurants:settings")
    session = stripe.billing_portal.Session.create(
        customer=restaurant.stripe_customer_id,
        return_url=f"{settings.SITE_URL}/dashboard/settings/",
    )
    return redirect(session.url)
