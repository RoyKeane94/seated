import uuid

from django.db import models

from restaurants.models import Restaurant, Service, Table


class Booking(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True)
    combined_tables = models.ManyToManyField(Table, blank=True, related_name="combined_bookings")

    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=20, blank=True)
    party_size = models.PositiveIntegerField()

    date = models.DateField()
    time = models.TimeField()
    notes = models.TextField(blank=True)

    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No Show"),
        (STATUS_COMPLETED, "Completed"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)

    SOURCE_ONLINE = "online"
    SOURCE_PHONE = "phone"
    SOURCE_WALKIN = "walkin"
    SOURCE_CHOICES = [
        (SOURCE_ONLINE, "Online booking"),
        (SOURCE_PHONE, "Phone booking"),
        (SOURCE_WALKIN, "Walk-in"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_ONLINE)

    cancel_token = models.UUIDField(default=uuid.uuid4, unique=True)
    modify_token = models.UUIDField(default=uuid.uuid4, unique=True)

    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time"]

    def get_cancel_url(self):
        return f"/booking/cancel/{self.cancel_token}/"

    def get_modify_url(self):
        return f"/booking/modify/{self.modify_token}/"

    def __str__(self):
        return f"{self.guest_name} - {self.party_size} covers - {self.date} {self.time}"


class EmailLog(models.Model):
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.SET_NULL)
    restaurant = models.ForeignKey(Restaurant, null=True, blank=True, on_delete=models.SET_NULL)
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    kind = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=[("sent", "Sent"), ("failed", "Failed")])
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
