from django.urls import path

from .views import (
    SeatedLoginView,
    SeatedLogoutView,
    onboarding_step1,
    onboarding_step2,
    onboarding_step3,
    onboarding_step4,
    signup,
)

app_name = "accounts"

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("signup/setup/step-1/", onboarding_step1, name="onboarding_step1"),
    path("signup/setup/step-2/", onboarding_step2, name="onboarding_step2"),
    path("signup/setup/step-3/", onboarding_step3, name="onboarding_step3"),
    path("signup/setup/step-4/", onboarding_step4, name="onboarding_step4"),
    path("login/", SeatedLoginView.as_view(), name="login"),
    path("logout/", SeatedLogoutView.as_view(), name="logout"),
]
