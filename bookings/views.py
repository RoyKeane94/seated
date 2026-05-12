import json
import secrets
from datetime import datetime, timedelta

import stripe
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods

from bookings.engine import get_available_slots
from bookings.forms import BookingCreateForm, BookingModifyForm
from bookings.models import Booking
from bookings.services import (
    build_restaurant_payload,
    invalidate_slots_cache,
    pick_service_and_assignment,
    register_slots_cache_key,
)
from bookings.tasks import send_cancellation_email, send_confirmation_email
from restaurants.models import Restaurant

stripe.api_key = settings.STRIPE_SECRET_KEY


def _rate_limit(request, key_base, limit=50, period=60):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"{key_base}:{ip}:{timezone.now().strftime('%Y%m%d%H%M')}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=period)
    return True


def booking_page(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not restaurant.subscription_active:
        return render(
            request,
            "bookings/restaurant_not_live.html",
            {"restaurant": restaurant},
            status=503,
        )
    if "widget_session_token" not in request.session:
        request.session["widget_session_token"] = secrets.token_urlsafe(20)
    if request.method == "POST":
        form = BookingCreateForm(request.POST)
        if form.is_valid():
            booking = create_booking_atomic(restaurant, form.cleaned_data)
            if booking:
                send_confirmation_email.delay(booking.id)
                return redirect("bookings:booking_success", slug=restaurant.slug, booking_id=booking.id)
            form.add_error(None, "This slot is no longer available. Please choose another time.")
    else:
        form = BookingCreateForm(initial={"party_size": 2})
    return render(
        request,
        "bookings/booking_page.html",
        {
            "restaurant": restaurant,
            "form": form,
            "embedded": request.GET.get("embedded") == "true",
            "widget_session_token": request.session["widget_session_token"],
        },
    )


def booking_success(request, slug, booking_id):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    booking = get_object_or_404(Booking, pk=booking_id, restaurant=restaurant)
    return render(request, "bookings/booking_success.html", {"restaurant": restaurant, "booking": booking})


def booking_ics(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    start = datetime.combine(booking.date, booking.time)
    end = start + timedelta(minutes=booking.service.turn_time_minutes if booking.service else 90)
    content = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Seated//Booking//EN",
            "BEGIN:VEVENT",
            f"UID:seated-booking-{booking.id}@seated.co",
            f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{booking.restaurant.name} reservation",
            f"DESCRIPTION:Party size {booking.party_size}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    response = HttpResponse(content, content_type="text/calendar")
    response["Content-Disposition"] = f'attachment; filename="booking-{booking.id}.ics"'
    return response


def booking_cancel(request, cancel_token):
    booking = get_object_or_404(Booking, cancel_token=cancel_token)
    if request.method == "POST":
        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        invalidate_slots_cache(booking.restaurant.slug)
        send_cancellation_email.delay(booking.id)
        return redirect("bookings:booking_cancel", cancel_token=cancel_token)
    return render(request, "bookings/booking_cancel.html", {"booking": booking})


def booking_modify(request, modify_token):
    booking = get_object_or_404(Booking, modify_token=modify_token)
    if request.method == "POST":
        form = BookingModifyForm(request.POST, instance=booking)
        if form.is_valid():
            data = form.cleaned_data
            updated = create_booking_atomic(
                booking.restaurant,
                {
                    "guest_name": booking.guest_name,
                    "guest_email": booking.guest_email,
                    "guest_phone": booking.guest_phone,
                    "party_size": data["party_size"],
                    "date": data["date"],
                    "time": data["time"],
                    "notes": data.get("notes", ""),
                    "source": booking.source,
                },
                update_booking=booking,
            )
            if updated:
                send_confirmation_email.delay(booking.id)
                return redirect("bookings:booking_success", slug=booking.restaurant.slug, booking_id=booking.id)
            form.add_error(None, "Requested new time is unavailable.")
    else:
        form = BookingModifyForm(instance=booking)
    return render(request, "bookings/booking_modify.html", {"booking": booking, "form": form})


@require_http_methods(["GET"])
def widget_api(request, slug):
    if not _rate_limit(request, "widget-api"):
        return JsonResponse({"error": "rate_limited"}, status=429)
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not restaurant.subscription_active:
        return JsonResponse({"error": "restaurant_not_live"}, status=503)
    date_str = request.GET.get("date")
    party_size = int(request.GET.get("party", "2"))
    if not date_str:
        return JsonResponse({"error": "date is required"}, status=400)
    date_value = parse_date(date_str)
    if not date_value:
        return JsonResponse({"error": "invalid date"}, status=400)
    key = f"slots_{slug}_{date_str}_{party_size}"
    slots = cache.get(key)
    if slots is None:
        payload = build_restaurant_payload(restaurant)
        slots = get_available_slots(payload, date_value, party_size)
        cache.set(key, slots, timeout=30)
        register_slots_cache_key(slug, key)
    response = JsonResponse({"slots": slots})
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_protect
@require_http_methods(["POST"])
def booking_api(request, slug):
    if not _rate_limit(request, "booking-api"):
        return JsonResponse({"error": "rate_limited"}, status=429)
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not restaurant.subscription_active:
        return JsonResponse({"error": "restaurant_not_live"}, status=503)
    widget_session_header = request.headers.get("X-Widget-Session")
    session_token = request.session.get("widget_session_token")
    if not widget_session_header or not session_token or widget_session_header != session_token:
        return JsonResponse({"error": "invalid_widget_session"}, status=403)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)
    if int(data.get("party_size", 0)) > restaurant.max_party_size:
        return JsonResponse({"error": "party_size_exceeds_limit"}, status=400)
    booking_date = parse_date(data.get("date", ""))
    if not booking_date:
        return JsonResponse({"error": "invalid_date"}, status=400)
    try:
        booking_time = datetime.strptime(data["time"], "%H:%M").time()
    except (KeyError, ValueError):
        return JsonResponse({"error": "invalid_time"}, status=400)
    booking = create_booking_atomic(
        restaurant,
        {
            "guest_name": data.get("guest_name", ""),
            "guest_email": data.get("guest_email", ""),
            "guest_phone": data.get("guest_phone", ""),
            "party_size": int(data["party_size"]),
            "date": booking_date,
            "time": booking_time,
            "notes": data.get("notes", ""),
            "source": Booking.SOURCE_ONLINE,
        },
    )
    if not booking:
        return JsonResponse({"error": "slot_unavailable"}, status=409)
    send_confirmation_email.delay(booking.id)
    return JsonResponse({"success": True, "booking_id": booking.id})


def create_booking_atomic(restaurant, data, update_booking=None):
    if data["party_size"] > restaurant.max_party_size:
        return None
    with transaction.atomic():
        restaurant = Restaurant.objects.select_for_update().get(pk=restaurant.pk)
        list(restaurant.tables.select_for_update().all())
        list(restaurant.bookings.filter(status=Booking.STATUS_CONFIRMED, date=data["date"]).select_for_update().all())
        payload = build_restaurant_payload(
            restaurant,
            exclude_booking_id=update_booking.pk if update_booking else None,
        )
        service_id, assignment = pick_service_and_assignment(payload, data["date"], data["time"], data["party_size"])
        if not assignment or not service_id:
            return None

        service = restaurant.services.get(pk=service_id)
        table = restaurant.tables.get(pk=assignment["table_id"])
        combined_tables_qs = restaurant.tables.filter(pk__in=assignment["combined_table_ids"])
        if update_booking:
            booking = update_booking
            booking.party_size = data["party_size"]
            booking.date = data["date"]
            booking.time = data["time"]
            booking.notes = data.get("notes", "")
            booking.service = service
            booking.table = table
            booking.status = Booking.STATUS_CONFIRMED
            booking.save()
            booking.combined_tables.set(combined_tables_qs)
        else:
            booking = Booking.objects.create(
                restaurant=restaurant,
                service=service,
                table=table,
                guest_name=data["guest_name"],
                guest_email=data["guest_email"],
                guest_phone=data.get("guest_phone", ""),
                party_size=data["party_size"],
                date=data["date"],
                time=data["time"],
                notes=data.get("notes", ""),
                source=data.get("source", Booking.SOURCE_ONLINE),
            )
            booking.combined_tables.set(combined_tables_qs)
        invalidate_slots_cache(restaurant.slug)
        return booking


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        return HttpResponseBadRequest("Invalid webhook")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        restaurant = Restaurant.objects.filter(stripe_customer_id=session.get("customer")).first()
        if restaurant:
            restaurant.subscription_active = True
            restaurant.stripe_subscription_id = session.get("subscription", "")
            restaurant.save(update_fields=["subscription_active", "stripe_subscription_id"])
    if event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        restaurant = Restaurant.objects.filter(stripe_subscription_id=subscription.get("id")).first()
        if restaurant:
            restaurant.subscription_active = subscription.get("status") in {"active", "trialing"}
            price_id = (
                subscription.get("items", {})
                .get("data", [{}])[0]
                .get("price", {})
                .get("id", "")
            )
            if price_id == settings.STRIPE_PRICE_WIDGET:
                restaurant.plan = Restaurant.PLAN_WIDGET
            elif price_id == settings.STRIPE_PRICE_LINK:
                restaurant.plan = Restaurant.PLAN_LINK
            restaurant.save(update_fields=["subscription_active", "plan"])
    if event["type"] in {"customer.subscription.deleted", "invoice.payment_failed"}:
        subscription = event["data"]["object"]
        subscription_id = subscription.get("id") or subscription.get("subscription")
        restaurant = Restaurant.objects.filter(stripe_subscription_id=subscription_id).first()
        if restaurant:
            restaurant.subscription_active = False
            restaurant.save(update_fields=["subscription_active"])

    return HttpResponse(status=200)
