import hashlib
import json
from collections import OrderedDict

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from restaurants.models import Restaurant


def username_for_email(email: str) -> str:
    """Store email as username when it fits; otherwise a stable short hash."""
    email = email.strip().lower()
    if len(email) <= User._meta.get_field("username").max_length:
        return email
    return hashlib.sha256(email.encode()).hexdigest()[:32]


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Email", required=True)
    plan = forms.ChoiceField(
        label="Choose your plan",
        choices=Restaurant.PLAN_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "plan-choice-list"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.setdefault("class", "plan-choice-list")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "input")
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "rounded-none")
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", "input")
                field.widget.attrs.setdefault("rows", "4")
            else:
                field.widget.attrs.setdefault("class", "input")
        self.fields["password2"].label = "Confirm password"
        self.fields = OrderedDict((k, self.fields[k]) for k in ("email", "password1", "password2", "plan"))
        self.fields["password1"].help_text = "Your password must contain at least 8 characters."
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")
        if not self.is_bound:
            self.fields["plan"].initial = Restaurant.PLAN_LINK

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        uname = username_for_email(email)
        if User.objects.filter(username__iexact=uname).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = username_for_email(self.cleaned_data["email"])
        if commit:
            user.save()
        return user


class SeatedLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget = forms.EmailInput(
            attrs={
                "class": "input",
                "autocomplete": "email",
            }
        )
        self.fields["password"].widget.attrs.setdefault("class", "input")
        self.fields["password"].widget.attrs.setdefault("autocomplete", "current-password")


class OnboardingRestaurantForm(forms.Form):
    name = forms.CharField(label="Restaurant name", max_length=200)
    address_line1 = forms.CharField(label="Address line 1", max_length=255, required=False)
    postcode = forms.CharField(max_length=20, required=False)
    phone = forms.CharField(label="Phone", max_length=20, required=False)
    email = forms.EmailField(label="Booking contact email", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "input"})
        self.fields["address_line1"].widget.attrs.update(
            {"class": "input", "placeholder": "14 Exmouth Market"}
        )
        self.fields["postcode"].widget.attrs.update({"class": "input", "placeholder": "EC1R 4QE"})
        self.fields["phone"].widget.attrs.update({"class": "input", "placeholder": "020 7000 0000"})
        self.fields["email"].widget.attrs.update(
            {"class": "input onboarding-input-account-email", "autocomplete": "email"}
        )


class OnboardingTablesForm(forms.Form):
    tables_json = forms.CharField(widget=forms.HiddenInput)
    max_party_size = forms.TypedChoiceField(
        label="Max guests per online booking",
        coerce=int,
        choices=[(n, str(n)) for n in range(1, 41)],
        initial=Restaurant._meta.get_field("max_party_size").default,
        help_text="Anyone who needs more seats than this must ring or email — the booking page only accepts parties up to this size.",
        widget=forms.HiddenInput(),
    )

    def clean_tables_json(self):
        raw = self.cleaned_data["tables_json"]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Invalid table data.") from exc
        if not isinstance(payload, list) or not payload:
            raise forms.ValidationError("Add at least one table.")
        return payload


class OnboardingServicesForm(forms.Form):
    services_json = forms.CharField(widget=forms.HiddenInput)

    def clean_services_json(self):
        raw = self.cleaned_data["services_json"]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Invalid service data.") from exc
        if not isinstance(payload, list) or not payload:
            raise forms.ValidationError("Add at least one service.")
        return payload
