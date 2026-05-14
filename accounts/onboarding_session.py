"""Build onboarding session payloads from existing restaurant data."""

from __future__ import annotations

from restaurants.models import Restaurant, Service


def build_onboarding_session_payload(restaurant: Restaurant) -> dict:
    tables_ordered = list(restaurant.tables.all().order_by("seats", "label", "pk"))
    pk_to_local = {t.pk: f"t{i + 1}" for i, t in enumerate(tables_ordered)}
    tables_payload = []
    for i, table in enumerate(tables_ordered):
        combine_ids = sorted(
            {pk_to_local[o.pk] for o in table.combine_with.all() if o.pk in pk_to_local},
            key=lambda lid: int(lid[1:]),
        )
        tables_payload.append(
            {
                "local_id": f"t{i + 1}",
                "label": table.label,
                "seats": table.seats,
                "is_combinable": table.is_combinable,
                "combine_with": combine_ids,
            }
        )

    services_payload = []
    for svc in restaurant.services.all().order_by("start_time", "pk"):
        services_payload.append(
            {
                "name": svc.name,
                "days_of_week": list(svc.days_of_week) if svc.days_of_week else [],
                "start_time": svc.start_time.strftime("%H:%M"),
                "end_time": svc.end_time.strftime("%H:%M"),
                "turn_time_minutes": svc.turn_time_minutes,
                "sitting_mode": svc.sitting_mode or Service.SITTING_FLEXIBLE,
                "fixed_sitting_times": svc.fixed_sitting_times or [],
                "slot_interval_minutes": svc.slot_interval_minutes,
            }
        )

    return {
        "plan": restaurant.plan,
        "restaurant": {
            "name": restaurant.name,
            "address_line1": restaurant.address_line1 or "",
            "postcode": restaurant.postcode or "",
            "phone": restaurant.phone or "",
            "email": restaurant.email or "",
        },
        "max_party_size": restaurant.max_party_size,
        "tables": tables_payload,
        "services": services_payload,
    }


def apply_onboarding_session_from_restaurant(request, restaurant: Restaurant) -> None:
    request.session["onboarding"] = build_onboarding_session_payload(restaurant)
    request.session.modified = True
