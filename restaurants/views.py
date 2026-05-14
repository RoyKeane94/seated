from collections import OrderedDict
from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, TemplateView, UpdateView

from bookings.services import invalidate_slots_cache
from bookings.models import Booking
from accounts.views import ONBOARDING_SIDEBAR_STEPS
from restaurants.forms import BookingDashboardForm, ClosedDateForm, RestaurantForm, ServiceForm, TableForm
from restaurants.models import ClosedDate, Restaurant, Service, Table

stripe.api_key = settings.STRIPE_SECRET_KEY


class OwnerRequiredMixin(LoginRequiredMixin):
    def get_restaurant(self):
        return get_object_or_404(Restaurant, owner=self.request.user)


def _booking_groups_for_day(bookings):
    """Preserve first-seen service order while grouping by service."""
    groups = OrderedDict()
    for booking in bookings:
        sid = booking.service_id if booking.service_id else 0
        if sid not in groups:
            groups[sid] = {"service": booking.service, "bookings": []}
        groups[sid]["bookings"].append(booking)
    return list(groups.values())


class DashboardTodayView(OwnerRequiredMixin, TemplateView):
    template_name = "restaurants/dashboard_today.html"

    def _parse_dashboard_date(self):
        raw = self.request.GET.get("date")
        fallback = timezone.localdate()
        if not raw:
            return fallback
        parsed = parse_date(raw)
        return parsed if parsed else fallback

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        restaurant = self.get_restaurant()
        booking_date = self._parse_dashboard_date()
        today = timezone.localdate()
        bookings = list(
            Booking.objects.filter(restaurant=restaurant, date=booking_date)
            .select_related("table", "service")
            .prefetch_related("combined_tables")
            .order_by("time")
        )

        booking_count = sum(
            1 for b in bookings if b.status not in (Booking.STATUS_CANCELLED,)
        )
        covers_confirmed = sum(
            b.party_size for b in bookings if b.status == Booking.STATUS_CONFIRMED
        )
        no_show_count = sum(1 for b in bookings if b.status == Booking.STATUS_NO_SHOW)

        qs_date = booking_date.strftime("%Y-%m-%d")
        context.update(
            {
                "restaurant": restaurant,
                "today": today,
                "booking_date": booking_date,
                "dashboard_date_param": qs_date,
                "is_dashboard_today": booking_date == today,
                "prev_date": booking_date - timedelta(days=1),
                "next_date": booking_date + timedelta(days=1),
                "bookings": bookings,
                "booking_groups": _booking_groups_for_day(bookings),
                "stat_booking_count": booking_count,
                "stat_covers_confirmed": covers_confirmed,
                "stat_no_show_count": no_show_count,
                "onboarding_sidebar_steps": ONBOARDING_SIDEBAR_STEPS,
            }
        )
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
    rd = parse_date(request.POST.get("dashboard_date") or "")
    qs = f"?date={rd.strftime('%Y-%m-%d')}" if rd else ""
    return redirect(f"{reverse('restaurants:dashboard')}{qs}")


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
def edit_onboarding_step(request, step: int):
    if step not in (1, 2, 3, 4):
        return redirect("restaurants:dashboard")
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    from accounts.onboarding_session import apply_onboarding_session_from_restaurant

    apply_onboarding_session_from_restaurant(request, restaurant)
    url_names = {
        1: "accounts:onboarding_step1",
        2: "accounts:onboarding_step2",
        3: "accounts:onboarding_step3",
        4: "accounts:onboarding_step4",
    }
    return redirect(url_names[step])


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
