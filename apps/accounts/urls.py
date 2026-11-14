from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from .views import (
    AccountLoginView,
    AccountPasswordResetConfirmView,
    AccountPasswordResetDoneView,
    AccountPasswordResetView,
    dashboard,
    profile,
    send_test_email,
    signup,
    signup_organization,
    signup_verify,
)

app_name = "accounts"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("acceso/", AccountLoginView.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("cuenta/configuracion/", profile, name="profile"),
    path("cuenta/configuracion/correo-de-prueba/", send_test_email, name="send_test_email"),
    path("registro/", signup, name="signup"),
    path("registro/verificar/", signup_verify, name="signup_verify"),
    path("registro/organizacion/", signup_organization, name="signup_organization"),
    path("recuperar/", AccountPasswordResetView.as_view(), name="password_reset"),
    path("recuperar/enviado/", AccountPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "recuperar/<uidb64>/<token>/",
        AccountPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/completado/",
        RedirectView.as_view(pattern_name="accounts:login"),
        name="password_reset_complete",
    ),
]
