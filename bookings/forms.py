from django import forms

from .models import Booking


class BookingCreateForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "input"}))
    time = forms.TimeField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "selected-time"}),
    )

    class Meta:
        model = Booking
        fields = [
            "date",
            "party_size",
            "time",
            "guest_name",
            "guest_email",
            "guest_phone",
            "notes",
        ]
        widgets = {
            "guest_name": forms.TextInput(attrs={"class": "input"}),
            "guest_email": forms.EmailInput(attrs={"class": "input"}),
            "guest_phone": forms.TextInput(attrs={"class": "input"}),
            "party_size": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }


class BookingModifyForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "input"}))

    class Meta:
        model = Booking
        fields = ["party_size", "date", "time", "notes"]
        widgets = {
            "party_size": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "time": forms.TimeInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }
