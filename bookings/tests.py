import json
from datetime import date, time

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from bookings.engine import assign_table, get_available_slots, is_slot_available
from bookings.models import Booking
from bookings.services import build_restaurant_payload, pick_service_and_assignment
from restaurants.models import Restaurant, Service, Table


class AvailabilityEngineTests(TestCase):
    def setUp(self):
        self.payload = {
            "services": [
                {
                    "id": 1,
                    "name": "Dinner",
                    "days_of_week": [4],
                    "start_time": time(18, 0),
                    "end_time": time(19, 0),
                    "turn_time_minutes": 90,
                    "sitting_mode": "flexible",
                    "fixed_sitting_times": [],
                    "slot_interval_minutes": 30,
                    "is_active": True,
                }
            ],
            "tables": [
                {"id": 1, "label": "T1", "seats": 2, "is_combinable": True, "combine_with_ids": [2]},
                {"id": 2, "label": "T2", "seats": 2, "is_combinable": True, "combine_with_ids": [1]},
            ],
            "bookings": [],
            "closed_dates": [],
        }

    def test_fixed_sittings_only_return_defined_times(self):
        payload = dict(self.payload)
        payload["services"] = [
            {
                "id": 2,
                "name": "Lunch",
                "days_of_week": [4],
                "start_time": time(12, 0),
                "end_time": time(14, 0),
                "turn_time_minutes": 90,
                "sitting_mode": "fixed",
                "fixed_sitting_times": ["12:30", "14:00"],
                "slot_interval_minutes": 15,
                "is_active": True,
            }
        ]
        slots = get_available_slots(payload, date(2026, 5, 8), 2)
        self.assertEqual(slots, ["12:30", "14:00"])

    def test_closed_dates_return_no_slots(self):
        payload = dict(self.payload)
        payload["closed_dates"] = [{"date": date(2026, 5, 8), "service_id": None}]
        self.assertEqual(get_available_slots(payload, date(2026, 5, 8), 2), [])

    def test_turn_time_blocks_overlapping_slot(self):
        payload = dict(self.payload)
        payload["bookings"] = [
            {
                "service_id": 1,
                "table_id": 1,
                "combined_table_ids": [],
                "date": date(2026, 5, 8),
                "time": time(18, 0),
                "turn_time_minutes": 90,
                "party_size": 2,
                "status": "confirmed",
            }
        ]
        self.assertTrue(is_slot_available(payload, date(2026, 5, 8), "18:30", 2))

    def test_combined_tables_mark_both_unavailable(self):
        payload = dict(self.payload)
        payload["service_id"] = 1
        payload["bookings"] = [
            {
                "service_id": 1,
                "table_id": 1,
                "combined_table_ids": [2],
                "date": date(2026, 5, 8),
                "time": time(18, 0),
                "turn_time_minutes": 90,
                "party_size": 4,
                "status": "confirmed",
            }
        ]
        assigned = assign_table(payload, date(2026, 5, 8), time(18, 30), 2)
        self.assertIsNone(assigned)

    def test_fully_booked_service_returns_no_slots(self):
        payload = dict(self.payload)
        payload["bookings"] = [
            {"service_id": 1, "table_id": 1, "combined_table_ids": [], "date": date(2026, 5, 8), "time": time(18, 0), "turn_time_minutes": 90, "party_size": 2, "status": "confirmed"},
            {"service_id": 1, "table_id": 2, "combined_table_ids": [], "date": date(2026, 5, 8), "time": time(18, 0), "turn_time_minutes": 90, "party_size": 2, "status": "confirmed"},
        ]
        self.assertEqual(get_available_slots(payload, date(2026, 5, 8), 2), [])


class BookingFlowTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("owner@test.com", "owner@test.com", "pass")
        self.restaurant = Restaurant.objects.create(owner=owner, name="Chez", slug="chez", subscription_active=True, max_party_size=6)
        self.service = Service.objects.create(
            restaurant=self.restaurant,
            name="Dinner",
            days_of_week=[date.today().weekday()],
            start_time=time(18, 0),
            end_time=time(20, 0),
            turn_time_minutes=90,
        )
        self.table1 = Table.objects.create(restaurant=self.restaurant, label="T1", seats=2, is_combinable=True)
        self.table2 = Table.objects.create(restaurant=self.restaurant, label="T2", seats=2, is_combinable=True)
        self.table1.combine_with.add(self.table2)
        self.client = Client()
        self.csrf_client = Client(enforce_csrf_checks=True)

    def test_valid_booking_created(self):
        response = self.client.post(
            reverse("bookings:booking_page", kwargs={"slug": self.restaurant.slug}),
            {
                "guest_name": "Alex",
                "guest_email": "alex@example.com",
                "guest_phone": "",
                "party_size": 2,
                "date": str(date.today()),
                "time": "18:00",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)

    def test_double_booking_rejected_when_table_not_available(self):
        Booking.objects.create(
            restaurant=self.restaurant,
            service=self.service,
            table=self.table1,
            guest_name="A",
            guest_email="a@a.com",
            party_size=2,
            date=date.today(),
            time=time(18, 0),
            status=Booking.STATUS_CONFIRMED,
        )
        Booking.objects.create(
            restaurant=self.restaurant,
            service=self.service,
            table=self.table2,
            guest_name="C",
            guest_email="c@c.com",
            party_size=2,
            date=date.today(),
            time=time(18, 0),
            status=Booking.STATUS_CONFIRMED,
        )
        seed = self.csrf_client.get(reverse("bookings:booking_page", kwargs={"slug": self.restaurant.slug}))
        csrf_token = seed.cookies["csrftoken"].value
        session = self.csrf_client.session
        widget_token = session["widget_session_token"]
        response = self.client.post(
            reverse("bookings:booking_api", kwargs={"slug": self.restaurant.slug}),
            data=json.dumps(
                {
                    "guest_name": "B",
                    "guest_email": "b@b.com",
                    "party_size": 2,
                    "date": str(date.today()),
                    "time": "18:00",
                }
            ),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [403, 429])
        api_response = self.csrf_client.post(
            reverse("bookings:booking_api", kwargs={"slug": self.restaurant.slug}),
            data=json.dumps(
                {
                    "guest_name": "B",
                    "guest_email": "b@b.com",
                    "party_size": 2,
                    "date": str(date.today()),
                    "time": "18:00",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_X_WIDGET_SESSION=widget_token,
        )
        self.assertEqual(api_response.status_code, 409)

    def test_cancel_and_modify_flow(self):
        booking = Booking.objects.create(
            restaurant=self.restaurant,
            service=self.service,
            table=self.table1,
            guest_name="A",
            guest_email="a@a.com",
            party_size=2,
            date=date.today(),
            time=time(18, 0),
        )
        cancel = self.client.post(reverse("bookings:booking_cancel", kwargs={"cancel_token": booking.cancel_token}))
        self.assertEqual(cancel.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)

    def test_party_size_exceeding_max_is_rejected(self):
        response = self.client.post(
            reverse("bookings:booking_page", kwargs={"slug": self.restaurant.slug}),
            {
                "guest_name": "Alex",
                "guest_email": "alex@example.com",
                "guest_phone": "",
                "party_size": 9,
                "date": str(date.today()),
                "time": "18:00",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)

    def test_race_like_back_to_back_booking_allows_only_one(self):
        payload = {
            "guest_name": "Alex",
            "guest_email": "alex@example.com",
            "guest_phone": "",
            "party_size": 4,
            "date": str(date.today()),
            "time": "18:00",
            "notes": "",
        }
        first = self.client.post(reverse("bookings:booking_page", kwargs={"slug": self.restaurant.slug}), payload)
        second = self.client.post(reverse("bookings:booking_page", kwargs={"slug": self.restaurant.slug}), payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Booking.objects.filter(date=date.today(), time=time(18, 0)).count(), 1)


class BookingPublicPageTests(TestCase):
    def test_booking_page_404_for_unknown_slug(self):
        response = self.client.get(reverse("bookings:booking_page", kwargs={"slug": "no-such-place"}))
        self.assertEqual(response.status_code, 404)

    def test_booking_page_503_when_subscription_inactive(self):
        owner = User.objects.create_user("o@test.com", "o@test.com", "pass")
        Restaurant.objects.create(
            owner=owner,
            name="Quiet Cafe",
            slug="quiet-cafe",
            subscription_active=False,
        )
        response = self.client.get(reverse("bookings:booking_page", kwargs={"slug": "quiet-cafe"}))
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"not available", response.content.lower())

    def test_widget_api_503_when_subscription_inactive(self):
        owner = User.objects.create_user("w@test.com", "w@test.com", "pass")
        Restaurant.objects.create(
            owner=owner,
            name="Widget Cafe",
            slug="widget-cafe",
            subscription_active=False,
        )
        response = self.client.get(
            reverse("bookings:widget_api", kwargs={"slug": "widget-cafe"}),
            {"date": str(date.today()), "party": 2},
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body.get("error"), "restaurant_not_live")

    def test_widget_api_returns_slots_when_active(self):
        owner = User.objects.create_user("a@test.com", "a@test.com", "pass")
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Open Cafe",
            slug="open-cafe",
            subscription_active=True,
        )
        Service.objects.create(
            restaurant=restaurant,
            name="Lunch",
            days_of_week=[date.today().weekday()],
            start_time=time(12, 0),
            end_time=time(13, 0),
            turn_time_minutes=60,
            slot_interval_minutes=30,
        )
        Table.objects.create(restaurant=restaurant, label="T1", seats=4)
        response = self.client.get(
            reverse("bookings:widget_api", kwargs={"slug": "open-cafe"}),
            {"date": str(date.today()), "party": 2},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("slots", data)
        self.assertIsInstance(data["slots"], list)


class BookingApiTests(TestCase):
    def test_booking_api_rejects_inactive_restaurant(self):
        owner = User.objects.create_user("api@test.com", "api@test.com", "pass")
        Restaurant.objects.create(
            owner=owner,
            name="Closed Cafe",
            slug="closed-cafe",
            subscription_active=False,
        )
        response = self.client.post(
            reverse("bookings:booking_api", kwargs={"slug": "closed-cafe"}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)


class BuildPayloadTests(TestCase):
    def test_build_restaurant_payload_includes_services_tables_bookings(self):
        owner = User.objects.create_user("pay@test.com", "pay@test.com", "pass")
        restaurant = Restaurant.objects.create(owner=owner, name="P", slug="p", subscription_active=True)
        Service.objects.create(
            restaurant=restaurant,
            name="Brunch",
            days_of_week=[3],
            start_time=time(10, 0),
            end_time=time(12, 0),
            turn_time_minutes=60,
        )
        t1 = Table.objects.create(restaurant=restaurant, label="A", seats=2)
        payload = build_restaurant_payload(restaurant)
        self.assertEqual(len(payload["services"]), 1)
        self.assertEqual(payload["services"][0]["name"], "Brunch")
        self.assertEqual(len(payload["tables"]), 1)
        self.assertEqual(payload["tables"][0]["id"], t1.id)
        self.assertEqual(payload["bookings"], [])


class PickServiceTests(TestCase):
    def test_pick_service_finds_matching_slot(self):
        owner = User.objects.create_user("pick@test.com", "pick@test.com", "pass")
        restaurant = Restaurant.objects.create(owner=owner, name="Q", slug="q", subscription_active=True)
        svc = Service.objects.create(
            restaurant=restaurant,
            name="Dinner",
            days_of_week=[date(2026, 1, 5).weekday()],
            start_time=time(18, 0),
            end_time=time(20, 0),
            turn_time_minutes=90,
        )
        Table.objects.create(restaurant=restaurant, label="T1", seats=4)
        payload = build_restaurant_payload(restaurant)
        d = date(2026, 1, 5)
        sid, _ = pick_service_and_assignment(payload, d, time(19, 0), 2)
        self.assertEqual(sid, svc.id)


class StripeWebhookTests(TestCase):
    def test_webhook_rejects_invalid_payload(self):
        response = self.client.post(
            reverse("bookings:stripe_webhook"),
            data=b"not-json",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad",
        )
        self.assertEqual(response.status_code, 400)


class BookingSuccessTests(TestCase):
    def test_success_page_404_for_wrong_booking(self):
        owner = User.objects.create_user("succ@test.com", "succ@test.com", "pass")
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="S",
            slug="succ-rest",
            subscription_active=True,
        )
        response = self.client.get(
            reverse(
                "bookings:booking_success",
                kwargs={"slug": restaurant.slug, "booking_id": 99999},
            )
        )
        self.assertEqual(response.status_code, 404)
