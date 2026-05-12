from datetime import datetime, timedelta


def _overlaps(existing_time, requested_time, turn_minutes):
    existing_start = datetime.combine(existing_time["date"], existing_time["time"])
    existing_end = existing_start + timedelta(minutes=existing_time["turn_time_minutes"])
    requested_start = datetime.combine(requested_time["date"], requested_time["time"])
    requested_end = requested_start + timedelta(minutes=turn_minutes)
    return requested_start < existing_end and existing_start < requested_end


def _is_closed(restaurant, date, service_id=None):
    for closed in restaurant.get("closed_dates", []):
        if closed["date"] == date and (closed.get("service_id") in (None, service_id)):
            return True
    return False


def _service_slots(service, date):
    if date.weekday() not in service["days_of_week"]:
        return []
    if service["sitting_mode"] == "fixed":
        return list(service.get("fixed_sitting_times", []))
    slots = []
    current = datetime.combine(date, service["start_time"])
    end = datetime.combine(date, service["end_time"])
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=service["slot_interval_minutes"])
    return slots


def _is_table_free(table_ids, bookings, date, time_value, turn_time):
    for booking in bookings:
        booked_table_ids = set()
        if booking.get("table_id"):
            booked_table_ids.add(booking["table_id"])
        booked_table_ids.update(booking.get("combined_table_ids", []))
        if not booked_table_ids.intersection(set(table_ids)):
            continue
        if _overlaps(
            {
                "date": booking["date"],
                "time": booking["time"],
                "turn_time_minutes": booking["turn_time_minutes"],
            },
            {"date": date, "time": time_value},
            turn_time,
        ):
            return False
    return True


def assign_table(restaurant, date, time, party_size):
    service = None
    for candidate in restaurant.get("services", []):
        if candidate["id"] == restaurant.get("service_id"):
            service = candidate
            break
    if not service:
        return None

    bookings = restaurant.get("bookings", [])
    tables = sorted(restaurant.get("tables", []), key=lambda t: (t["seats"], t["label"]))

    for table in tables:
        if table["seats"] >= party_size and _is_table_free([table["id"]], bookings, date, time, service["turn_time_minutes"]):
            return {"table_id": table["id"], "combined_table_ids": []}

    combinations = []
    for table in tables:
        if not table.get("is_combinable"):
            continue
        for pair_id in table.get("combine_with_ids", []):
            other = next((t for t in tables if t["id"] == pair_id), None)
            if not other:
                continue
            seats = table["seats"] + other["seats"]
            if seats >= party_size:
                combo_ids = sorted([table["id"], other["id"]])
                combinations.append((seats, combo_ids))

    seen = set()
    for _, combo_ids in sorted(combinations, key=lambda x: x[0]):
        key = tuple(combo_ids)
        if key in seen:
            continue
        seen.add(key)
        if _is_table_free(combo_ids, bookings, date, time, service["turn_time_minutes"]):
            return {"table_id": combo_ids[0], "combined_table_ids": combo_ids[1:]}

    return None


def get_available_slots(restaurant, date, party_size):
    slots = []
    for service in restaurant.get("services", []):
        if not service.get("is_active", True):
            continue
        if _is_closed(restaurant, date, service["id"]):
            continue
        for slot in _service_slots(service, date):
            time_value = datetime.strptime(slot, "%H:%M").time()
            payload = dict(restaurant)
            payload["service_id"] = service["id"]
            if assign_table(payload, date, time_value, party_size):
                slots.append(slot)
    return sorted(set(slots))


def is_slot_available(restaurant, date, time_str, party_size):
    return time_str in get_available_slots(restaurant, date, party_size)


def get_bookings_for_service(restaurant, date, service):
    return [
        booking
        for booking in restaurant.get("bookings", [])
        if booking["date"] == date and booking.get("service_id") == service["id"] and booking["status"] == "confirmed"
    ]


def get_covers_summary(restaurant, date):
    summary = {}
    total_capacity = sum(table["seats"] for table in restaurant.get("tables", []))
    for service in restaurant.get("services", []):
        if date.weekday() not in service["days_of_week"]:
            continue
        bookings = get_bookings_for_service(restaurant, date, service)
        booked = sum(booking["party_size"] for booking in bookings)
        summary[service["name"]] = {
            "booked": booked,
            "capacity": total_capacity,
            "remaining": max(total_capacity - booked, 0),
        }
    return summary
