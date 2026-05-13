import json
from datetime import datetime

import stripe
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.forms import (
    OnboardingRestaurantForm,
    OnboardingServicesForm,
    OnboardingTablesForm,
    SeatedLoginForm,
    SignupForm,
)
from restaurants.models import Restaurant
from restaurants.models import Service, Table

stripe.api_key = settings.STRIPE_SECRET_KEY


ONBOARDING_SIDEBAR_STEPS = [
    {"num": 1, "title": "Restaurant details", "desc": "Name, address, contact"},
    {"num": 2, "title": "Tables", "desc": "Covers, layout, turn times"},
    {"num": 3, "title": "Services", "desc": "Lunch, dinner, and when you're open"},
    {"num": 4, "title": "Go live", "desc": "Your booking page, ready to share"},
]


SIGNUP_PLAN_CARDS = [
    {
        "value": Restaurant.PLAN_LINK,
        "title": "Booking link",
        "price": "£50",
        "desc": "A hosted page you can share anywhere",
    },
    {
        "value": Restaurant.PLAN_WIDGET,
        "title": "Embedded widget",
        "price": "£60",
        "desc": "Bookings built into your own website",
    },
]


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            request.session["onboarding"] = {
                "plan": form.cleaned_data["plan"],
                "tables": [],
                "services": [],
            }
            login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
            return redirect("accounts:onboarding_step1")
    else:
        form = SignupForm()
    return render(
        request,
        "accounts/signup.html",
        {"form": form, "signup_plan_cards": SIGNUP_PLAN_CARDS},
    )


def _get_onboarding_data(request):
    return request.session.get("onboarding", {"plan": Restaurant.PLAN_LINK, "tables": [], "services": []})


def _onboarding_name_default(user):
    email = (user.email or "").strip()
    if "@" in email:
        local = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
        return local.title() if local else "My restaurant"
    return "My restaurant"


@login_required
def onboarding_step1(request):
    data = _get_onboarding_data(request)
    name_guess = _onboarding_name_default(request.user)
    initial = {
        "name": name_guess,
        "email": (request.user.email or "").strip(),
    }
    if request.method == "POST":
        form = OnboardingRestaurantForm(request.POST)
        if form.is_valid():
            data["restaurant"] = form.cleaned_data
            request.session["onboarding"] = data
            return redirect("accounts:onboarding_step2")
    else:
        form = OnboardingRestaurantForm(initial=initial)
    return render(
        request,
        "accounts/onboarding_step1.html",
        {"form": form, "step": 1, "onboarding_sidebar_steps": ONBOARDING_SIDEBAR_STEPS},
    )


@login_required
def onboarding_step2(request):
    data = _get_onboarding_data(request)
    if "restaurant" not in data:
        return redirect("accounts:onboarding_step1")
    if request.method == "POST":
        form = OnboardingTablesForm(request.POST)
        if form.is_valid():
            data["tables"] = form.cleaned_data["tables_json"]
            data["max_party_size"] = form.cleaned_data["max_party_size"]
            request.session["onboarding"] = data
            return redirect("accounts:onboarding_step3")
    else:
        form = OnboardingTablesForm(
            initial={
                "tables_json": json.dumps(data.get("tables", [])),
                "max_party_size": data.get(
                    "max_party_size",
                    Restaurant._meta.get_field("max_party_size").default,
                ),
            }
        )
    return render(
        request,
        "accounts/onboarding_step2.html",
        {
            "form": form,
            "step": 2,
            "table_count_options": range(1, 25),
            "onboarding_sidebar_steps": ONBOARDING_SIDEBAR_STEPS,
        },
    )


@login_required
def onboarding_step3(request):
    data = _get_onboarding_data(request)
    if "restaurant" not in data:
        return redirect("accounts:onboarding_step1")
    if request.method == "POST":
        form = OnboardingServicesForm(request.POST)
        if form.is_valid():
            data["services"] = form.cleaned_data["services_json"]
            request.session["onboarding"] = data
            return redirect("accounts:onboarding_step4")
    else:
        form = OnboardingServicesForm(initial={"services_json": json.dumps(data.get("services", []))})
    return render(
        request,
        "accounts/onboarding_step3.html",
        {"form": form, "step": 3, "onboarding_sidebar_steps": ONBOARDING_SIDEBAR_STEPS},
    )


@login_required
def onboarding_step4(request):
    data = _get_onboarding_data(request)
    if "restaurant" not in data:
        return redirect("accounts:onboarding_step1")
    if request.method == "POST":
        details = data["restaurant"]
        stripe_configured = bool(settings.STRIPE_SECRET_KEY)
        want_publish = request.POST.get("finish_action") == "publish"
        existing = Restaurant.objects.filter(owner=request.user).first()
        slug = Restaurant.alloc_unique_slug(details["name"], exclude_pk=existing.pk if existing else None)
        restaurant, _ = Restaurant.objects.update_or_create(
            owner=request.user,
            defaults={
                "name": details["name"],
                "slug": slug,
                "address_line1": details.get("address_line1", ""),
                "postcode": details.get("postcode", ""),
                "phone": details.get("phone", ""),
                "email": details.get("email", ""),
                "plan": data.get("plan", Restaurant.PLAN_LINK),
                "max_party_size": int(
                    data.get("max_party_size", Restaurant._meta.get_field("max_party_size").default)
                ),
                "booking_link_published": want_publish,
                # Booking pages require an active subscription; without Stripe (local dev) skip paywall.
                "subscription_active": not stripe_configured,
            },
        )

        restaurant.tables.all().delete()
        table_index = {}
        for item in data.get("tables", []):
            table = Table.objects.create(
                restaurant=restaurant,
                label=item["label"],
                seats=int(item["seats"]),
                is_combinable=bool(item.get("is_combinable")),
            )
            table_index[item["local_id"]] = table
        for item in data.get("tables", []):
            table = table_index[item["local_id"]]
            combine_with = [table_index[local] for local in item.get("combine_with", []) if local in table_index]
            table.combine_with.set(combine_with)

        restaurant.services.all().delete()
        for item in data.get("services", []):
            Service.objects.create(
                restaurant=restaurant,
                name=item["name"],
                days_of_week=item["days_of_week"],
                start_time=datetime.strptime(item["start_time"], "%H:%M").time(),
                end_time=datetime.strptime(item["end_time"], "%H:%M").time(),
                turn_time_minutes=int(item.get("turn_time_minutes", 90)),
                sitting_mode=item.get("sitting_mode", Service.SITTING_FLEXIBLE),
                fixed_sitting_times=item.get("fixed_sitting_times", []),
                slot_interval_minutes=int(item.get("slot_interval_minutes", 15)),
            )

        customer = stripe.Customer.create(email=request.user.email or "") if settings.STRIPE_SECRET_KEY else {"id": ""}
        restaurant.stripe_customer_id = customer.get("id", "")
        restaurant.save(update_fields=["stripe_customer_id"])
        request.session.pop("onboarding", None)
        if settings.STRIPE_SECRET_KEY:
            session = stripe.checkout.Session.create(
                customer=restaurant.stripe_customer_id,
                payment_method_types=["card"],
                mode="subscription",
                line_items=[
                    {
                        "price": settings.STRIPE_PRICE_WIDGET
                        if restaurant.plan == Restaurant.PLAN_WIDGET
                        else settings.STRIPE_PRICE_LINK,
                        "quantity": 1,
                    }
                ],
                success_url=f"{settings.SITE_URL}/dashboard/",
                cancel_url=f"{settings.SITE_URL}/signup/",
            )
            return redirect(session.url)
        return redirect("restaurants:dashboard")
    existing = Restaurant.objects.filter(owner=request.user).first()
    preview_booking_slug = Restaurant.alloc_unique_slug(
        data["restaurant"]["name"],
        exclude_pk=existing.pk if existing else None,
    )
    return render(
        request,
        "accounts/onboarding_step4.html",
        {
            "step": 4,
            "data": data,
            "preview_booking_slug": preview_booking_slug,
            "onboarding_sidebar_steps": ONBOARDING_SIDEBAR_STEPS,
        },
    )


class SeatedLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SeatedLoginForm


class SeatedLogoutView(LogoutView):
    pass
