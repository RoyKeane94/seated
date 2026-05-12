from datetime import datetime

from django.core.cache import cache

from bookings.engine import assign_table
from bookings.models import Booking


def build_restaurant_payload(restaurant, *, exclude_booking_id=None):
    services = list(
        restaurant.services.filter(is_active=True).values(
            "id",
            "name",
            "days_of_week",
            "start_time",
            "end_time",
            "turn_time_minutes",
            "sitting_mode",
            "fixed_sitting_times",
            "slot_interval_minutes",
            "is_active",
        )
    )
    tables = []
    for table in restaurant.tables.all().prefetch_related("combine_with"):
        tables.append(
            {
                "id": table.id,
                "label": table.label,
                "seats": table.seats,
                "is_combinable": table.is_combinable,
                "combine_with_ids": list(table.combine_with.values_list("id", flat=True)),
            }
        )

    bookings = []
    confirmed = restaurant.bookings.filter(status=Booking.STATUS_CONFIRMED).select_related("service").prefetch_related(
        "combined_tables"
    )
    if exclude_booking_id:
        confirmed = confirmed.exclude(pk=exclude_booking_id)
    for booking in confirmed:
        service_turn = booking.service.turn_time_minutes if booking.service else 90
        bookings.append(
            {
                "id": booking.id,
                "service_id": booking.service_id,
                "table_id": booking.table_id,
                "combined_table_ids": list(booking.combined_tables.values_list("id", flat=True)),
                "party_size": booking.party_size,
                "date": booking.date,
                "time": booking.time,
                "turn_time_minutes": service_turn,
                "status": booking.status,
            }
        )

    return {
        "id": restaurant.id,
        "services": services,
        "tables": tables,
        "bookings": bookings,
        "closed_dates": list(restaurant.closed_dates.values("date", "service_id")),
    }


def pick_service_and_assignment(payload, date, time_value, party_size):
    time_str = time_value.strftime("%H:%M")
    for service in payload["services"]:
        if date.weekday() not in service["days_of_week"]:
            continue
        if service["sitting_mode"] == "fixed":
            slots = set(service.get("fixed_sitting_times", []))
            if time_str not in slots:
                continue
        else:
            start = datetime.combine(date, service["start_time"])
            end = datetime.combine(date, service["end_time"])
            requested = datetime.combine(date, time_value)
            if requested < start or requested > end:
                continue
        scoped_payload = dict(payload)
        scoped_payload["service_id"] = service["id"]
        assignment = assign_table(scoped_payload, date, time_value, party_size)
        if assignment:
            return service["id"], assignment
    return None, None


def register_slots_cache_key(slug, key):
    index_key = f"slots_idx_{slug}"
    keys = cache.get(index_key, [])
    if key not in keys:
        keys.append(key)
        cache.set(index_key, keys, timeout=3600)


def invalidate_slots_cache(slug):
    index_key = f"slots_idx_{slug}"
    keys = cache.get(index_key, [])
    if keys:
        cache.delete_many(keys)
    cache.delete(index_key)
