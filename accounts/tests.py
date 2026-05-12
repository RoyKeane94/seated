import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.forms import OnboardingRestaurantForm, OnboardingServicesForm, OnboardingTablesForm, SignupForm
from restaurants.models import Restaurant, Service, Table


class SiteSmokeTests(TestCase):
    def test_home_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")


class SignupAndAuthTests(TestCase):
    def test_signup_creates_user_starts_onboarding(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "newchef@example.com",
                "password1": "notedible8chars",
                "password2": "notedible8chars",
                "plan": Restaurant.PLAN_LINK,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="newchef@example.com").exists())
        user = User.objects.get(email="newchef@example.com")
        self.assertEqual(user.username, "newchef@example.com")

    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user("newchef@example.com", "newchef@example.com", "pass12345")
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "newchef@example.com",
                "password1": "notedible8chars",
                "password2": "notedible8chars",
                "plan": Restaurant.PLAN_LINK,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue("already exists" in str(response.content).lower() or response.context["form"].errors)

    def test_login_with_email_succeeds(self):
        User.objects.create_user("chef@example.com", "chef@example.com", "mypassphrase")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "chef@example.com", "password": "mypassphrase"},
        )
        self.assertEqual(response.status_code, 302)

    def test_login_wrong_password(self):
        User.objects.create_user("chef@example.com", "chef@example.com", "mypassphrase")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "chef@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)

    def test_logout_redirects_home(self):
        User.objects.create_user("chef@example.com", "chef@example.com", "mypassphrase")
        self.client.login(username="chef@example.com", password="mypassphrase")
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse("home")) or response.url == "/")


class OnboardingFormTests(TestCase):
    def test_restaurant_form_has_no_slug_field(self):
        form = OnboardingRestaurantForm()
        self.assertNotIn("slug", form.fields)

    def test_restaurant_form_valid_minimal(self):
        form = OnboardingRestaurantForm(data={"name": "The Ivy"})
        self.assertTrue(form.is_valid())

    def test_tables_form_requires_non_empty_list(self):
        form = OnboardingTablesForm(data={"tables_json": "[]"})
        self.assertFalse(form.is_valid())

    def test_tables_form_accepts_valid_json(self):
        payload = json.dumps(
            [{"local_id": "t1", "label": "A", "seats": 2, "is_combinable": False, "combine_with": []}]
        )
        form = OnboardingTablesForm(data={"tables_json": payload})
        self.assertTrue(form.is_valid())

    def test_services_form_accepts_valid_json(self):
        payload = json.dumps(
            [
                {
                    "name": "Evening",
                    "days_of_week": [0, 1, 2],
                    "start_time": "18:00",
                    "end_time": "21:00",
                    "turn_time_minutes": 90,
                    "sitting_mode": "flexible",
                    "fixed_sitting_times": [],
                    "slot_interval_minutes": 15,
                }
            ]
        )
        form = OnboardingServicesForm(data={"services_json": payload})
        self.assertTrue(form.is_valid())


@override_settings(STRIPE_SECRET_KEY="")
class OnboardingFlowTests(TestCase):
    tables_payload = json.dumps(
        [{"local_id": "t1", "label": "Table 1", "seats": 4, "is_combinable": False, "combine_with": []}]
    )
    services_payload = json.dumps(
        [
            {
                "name": "Evening",
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "start_time": "18:00",
                "end_time": "21:00",
                "turn_time_minutes": 90,
                "sitting_mode": "flexible",
                "fixed_sitting_times": [],
                "slot_interval_minutes": 15,
            }
        ]
    )

    def test_full_onboarding_creates_restaurant_and_slug_from_name(self):
        client = Client()
        client.post(
            reverse("accounts:signup"),
            {
                "email": "flow@example.com",
                "password1": "notedible8chars",
                "password2": "notedible8chars",
                "plan": Restaurant.PLAN_LINK,
            },
        )
        user = User.objects.get(email="flow@example.com")
        self.assertFalse(Restaurant.objects.filter(owner=user).exists())

        client.post(
            reverse("accounts:onboarding_step1"),
            {
                "name": "The Bistro",
                "address_line1": "1 High St",
                "postcode": "NW1",
                "phone": "",
                "email": "",
            },
        )
        client.post(
            reverse("accounts:onboarding_step2"),
            {"tables_json": self.tables_payload},
        )
        client.post(
            reverse("accounts:onboarding_step3"),
            {"services_json": self.services_payload},
        )
        response = client.post(reverse("accounts:onboarding_step4"), {})
        self.assertEqual(response.status_code, 302)

        restaurant = Restaurant.objects.get(owner=user)
        self.assertEqual(restaurant.name, "The Bistro")
        self.assertEqual(restaurant.slug, "the-bistro")
        self.assertTrue(restaurant.subscription_active)
        self.assertEqual(restaurant.tables.count(), 1)
        self.assertEqual(restaurant.services.count(), 1)

    def test_step_two_redirects_if_step_one_not_done(self):
        client = Client()
        client.post(
            reverse("accounts:signup"),
            {
                "email": "skip@example.com",
                "password1": "notedible8chars",
                "password2": "notedible8chars",
                "plan": Restaurant.PLAN_LINK,
            },
        )
        response = client.get(reverse("accounts:onboarding_step2"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:onboarding_step1"))


class SignupFormUnitTests(TestCase):
    def test_signup_form_plan_choices(self):
        form = SignupForm()
        plans = {c[0] for c in form.fields["plan"].choices if c[0]}
        self.assertIn(Restaurant.PLAN_LINK, plans)
        self.assertIn(Restaurant.PLAN_WIDGET, plans)
