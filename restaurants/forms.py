from django import forms

from bookings.models import Booking
from .models import ClosedDate, Restaurant, Service, Table

_INPUT = {"class": "input"}
_TEXTAREA = {"class": "input", "rows": 4}


class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = [
            "name",
            "address_line1",
            "postcode",
            "phone",
            "email",
            "plan",
            "max_party_size",
            "timezone",
            "booking_confirmation_message",
        ]
        widgets = {
            "name": forms.TextInput(attrs=_INPUT),
            "address_line1": forms.TextInput(attrs=_INPUT),
            "postcode": forms.TextInput(attrs=_INPUT),
            "phone": forms.TextInput(attrs=_INPUT),
            "email": forms.EmailInput(attrs=_INPUT),
            "plan": forms.Select(attrs=_INPUT),
            "max_party_size": forms.NumberInput(attrs={**_INPUT, "min": 1}),
            "timezone": forms.TextInput(attrs=_INPUT),
            "booking_confirmation_message": forms.Textarea(attrs=_TEXTAREA),
        }


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ["label", "seats", "is_combinable", "combine_with"]
        widgets = {
            "label": forms.TextInput(attrs=_INPUT),
            "seats": forms.NumberInput(attrs={**_INPUT, "min": 1, "max": 24}),
            "is_combinable": forms.CheckboxInput(attrs={"class": "rounded-none"}),
            "combine_with": forms.SelectMultiple(attrs={**_INPUT, "size": 4}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "days_of_week",
            "start_time",
            "end_time",
            "turn_time_minutes",
            "sitting_mode",
            "fixed_sitting_times",
            "slot_interval_minutes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs=_INPUT),
            "days_of_week": forms.Textarea(attrs={**_TEXTAREA, "rows": 2}),
            "start_time": forms.TimeInput(attrs={**_INPUT, "type": "time"}),
            "end_time": forms.TimeInput(attrs={**_INPUT, "type": "time"}),
            "turn_time_minutes": forms.NumberInput(attrs={**_INPUT, "min": 15}),
            "sitting_mode": forms.Select(attrs=_INPUT),
            "fixed_sitting_times": forms.Textarea(attrs={**_TEXTAREA, "rows": 2}),
            "slot_interval_minutes": forms.NumberInput(attrs={**_INPUT, "min": 5}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded-none"}),
        }


class ClosedDateForm(forms.ModelForm):
    class Meta:
        model = ClosedDate
        fields = ["date", "reason", "all_day", "service"]
        widgets = {
            "date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "reason": forms.TextInput(attrs=_INPUT),
            "all_day": forms.CheckboxInput(attrs={"class": "rounded-none"}),
            "service": forms.Select(attrs=_INPUT),
        }


class BookingDashboardForm(forms.ModelForm):
    combined_tables = forms.ModelMultipleChoiceField(
        queryset=Table.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={**_INPUT, "size": 5}),
    )

    class Meta:
        model = Booking
        fields = [
            "guest_name",
            "guest_email",
            "guest_phone",
            "party_size",
            "date",
            "time",
            "notes",
            "status",
            "table",
            "combined_tables",
        ]
        widgets = {
            "guest_name": forms.TextInput(attrs=_INPUT),
            "guest_email": forms.EmailInput(attrs=_INPUT),
            "guest_phone": forms.TextInput(attrs=_INPUT),
            "party_size": forms.NumberInput(attrs={**_INPUT, "min": 1}),
            "date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "time": forms.TimeInput(attrs={**_INPUT, "type": "time"}),
            "notes": forms.Textarea(attrs=_TEXTAREA),
            "status": forms.Select(attrs=_INPUT),
            "table": forms.Select(attrs=_INPUT),
        }

    def __init__(self, *args, restaurant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if restaurant:
            table_qs = restaurant.tables.all()
            self.fields["table"].queryset = table_qs
            self.fields["combined_tables"].queryset = table_qs
