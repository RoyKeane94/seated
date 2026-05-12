from datetime import date, time

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from bookings.models import Booking
from restaurants.models import Restaurant, Service, Table


class RestaurantModelTests(TestCase):
    def test_save_assigns_slug_from_name_when_blank(self):
        owner = User.objects.create_user("slug1@test.com", "slug1@test.com", "pass")
        r = Restaurant(owner=owner, name="River Café", slug="")
        r.save()
        self.assertEqual(r.slug, "river-cafe")

    def test_alloc_unique_slug_avoids_collision(self):
        owner1 = User.objects.create_user("s1@test.com", "s1@test.com", "pass")
        owner2 = User.objects.create_user("s2@test.com", "s2@test.com", "pass")
        Restaurant.objects.create(owner=owner1, name="First", slug="same-name")
        slug = Restaurant.alloc_unique_slug("Same Name", exclude_pk=None)
        self.assertEqual(slug, "same-name-2")

        slug_existing = Restaurant.alloc_unique_slug("Same Name", exclude_pk=Restaurant.objects.get(slug="same-name").pk)
        self.assertEqual(slug_existing, "same-name")


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("dash@test.com", "dash@test.com", "pass")
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Dash House",
            slug="dash-house",
            subscription_active=True,
        )
        Service.objects.create(
            restaurant=self.restaurant,
            name="Dinner",
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            start_time=time(17, 0),
            end_time=time(22, 0),
            turn_time_minutes=90,
        )
        self.client = Client()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("restaurants:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_dashboard_ok_for_owner(self):
        self.client.login(username="dash@test.com", password="pass")
        response = self.client.get(reverse("restaurants:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_settings_shows_booking_link(self):
        self.client.login(username="dash@test.com", password="pass")
        response = self.client.get(reverse("restaurants:settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/book/dash-house/")

    def test_upcoming_dashboard_ok_for_owner(self):
        self.client.login(username="dash@test.com", password="pass")
        response = self.client.get(reverse("restaurants:dashboard_upcoming"))
        self.assertEqual(response.status_code, 200)

    def test_settings_post_updates_name(self):
        self.client.login(username="dash@test.com", password="pass")
        response = self.client.post(
            reverse("restaurants:settings"),
            {
                "name": "Renamed House",
                "address_line1": "",
                "postcode": "",
                "phone": "",
                "email": "",
                "plan": Restaurant.PLAN_LINK,
                "max_party_size": 8,
                "timezone": "Europe/London",
                "booking_confirmation_message": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.name, "Renamed House")

    def test_add_table_creates_row(self):
        self.client.login(username="dash@test.com", password="pass")
        response = self.client.post(
            reverse("restaurants:add_table"),
            {
                "label": "Patio",
                "seats": 6,
                "is_combinable": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.restaurant.tables.filter(label="Patio", seats=6).exists())


class DashboardOwnershipTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@test.com", "owner@test.com", "pass")
        self.other = User.objects.create_user("other@test.com", "other@test.com", "pass")
        self.restaurant = Restaurant.objects.create(owner=self.owner, name="Chez", slug="chez", subscription_active=True)
        self.service = Service.objects.create(
            restaurant=self.restaurant,
            name="Dinner",
            days_of_week=[date.today().weekday()],
            start_time=time(18, 0),
            end_time=time(21, 0),
            turn_time_minutes=90,
        )
        table = Table.objects.create(restaurant=self.restaurant, label="T1", seats=2)
        self.booking = Booking.objects.create(
            restaurant=self.restaurant,
            service=self.service,
            table=table,
            guest_name="Guest",
            guest_email="guest@test.com",
            party_size=2,
            date=date.today(),
            time=time(18, 0),
        )
        self.client = Client()

    def test_non_owner_cannot_mutate_booking_status(self):
        self.client.login(username="other@test.com", password="pass")
        response = self.client.post(
            reverse("restaurants:booking_status", kwargs={"pk": self.booking.pk, "status": "cancel"})
        )
        self.assertEqual(response.status_code, 404)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CONFIRMED)

    def test_owner_can_mark_booking_completed(self):
        self.client.login(username="owner@test.com", password="pass")
        response = self.client.post(
            reverse("restaurants:booking_status", kwargs={"pk": self.booking.pk, "status": "complete"})
        )
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_COMPLETED)
