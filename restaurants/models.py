from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


class Restaurant(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    postcode = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    PLAN_LINK = "link"
    PLAN_WIDGET = "widget"
    PLAN_CHOICES = [
        (PLAN_LINK, "Booking link\n£50/mo · one shareable URL"),
        (PLAN_WIDGET, "Embedded widget\n£60/mo · books on your website"),
    ]
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_LINK)

    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    subscription_active = models.BooleanField(default=False)
    booking_link_published = models.BooleanField(
        default=False,
        help_text="When False, guests cannot book via the public URL even if billing is active.",
    )

    booking_confirmation_message = models.TextField(
        blank=True,
        help_text="Custom message included in confirmation emails",
    )
    max_party_size = models.PositiveIntegerField(default=8)
    timezone = models.CharField(max_length=64, default="Europe/London")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def alloc_unique_slug(cls, name: str, exclude_pk=None) -> str:
        base_slug = slugify(name) or "restaurant"
        candidate = base_slug
        count = 2
        qs = cls.objects.filter(slug=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        while qs.exists():
            candidate = f"{base_slug}-{count}"
            count += 1
            qs = cls.objects.filter(slug=candidate)
            if exclude_pk is not None:
                qs = qs.exclude(pk=exclude_pk)
        return candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.alloc_unique_slug(self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    def get_booking_url(self):
        return f"/book/{self.slug}/"

    def __str__(self):
        return self.name


class Table(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="tables")
    label = models.CharField(max_length=50)
    seats = models.PositiveIntegerField()
    is_combinable = models.BooleanField(default=False)
    combine_with = models.ManyToManyField("self", blank=True, symmetrical=True)

    class Meta:
        ordering = ["seats", "label"]

    def __str__(self):
        return f"{self.restaurant.name} - {self.label} ({self.seats} seats)"


class Service(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=100)

    DAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]
    days_of_week = models.JSONField(default=list)

    start_time = models.TimeField()
    end_time = models.TimeField()
    turn_time_minutes = models.PositiveIntegerField(default=90)

    SITTING_FLEXIBLE = "flexible"
    SITTING_FIXED = "fixed"
    SITTING_CHOICES = [
        (SITTING_FLEXIBLE, "Flexible - rolling availability"),
        (SITTING_FIXED, "Fixed - set sitting times only"),
    ]
    sitting_mode = models.CharField(max_length=20, choices=SITTING_CHOICES, default=SITTING_FLEXIBLE)
    fixed_sitting_times = models.JSONField(
        default=list,
        blank=True,
        help_text="List of times as HH:MM strings",
    )

    slot_interval_minutes = models.PositiveIntegerField(default=15)
    is_active = models.BooleanField(default=True)

    def get_slots_for_date(self, date):
        if date.weekday() not in self.days_of_week:
            return []
        if self.sitting_mode == self.SITTING_FIXED:
            return self.fixed_sitting_times
        slots = []
        current = datetime.combine(date, self.start_time)
        end = datetime.combine(date, self.end_time)
        interval = timedelta(minutes=self.slot_interval_minutes)
        while current <= end:
            slots.append(current.strftime("%H:%M"))
            current += interval
        return slots

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class ClosedDate(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="closed_dates")
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    all_day = models.BooleanField(default=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.restaurant.name} closed {self.date}"
