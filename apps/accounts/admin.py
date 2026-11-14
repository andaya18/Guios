from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Organization, PendingSignup, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "sector", "is_active")
    search_fields = ("name", "domain")


class GuiosUserCreationForm(BaseUserCreationForm):
    """Django's default form asks for `username`; this project identifies users by email."""

    class Meta:
        model = User
        fields = ("email",)


class GuiosUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class GuiosUserAdmin(UserAdmin):
    """UserAdmin with every reference to `username` replaced by `email` (the model has no username)."""

    form = GuiosUserChangeForm
    add_form = GuiosUserCreationForm
    list_display = ("email", "first_name", "last_name", "role", "organization", "is_active")
    list_filter = ("role", "is_active", "is_staff", "organization")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "area")}),
        ("GUIOS", {"fields": ("role", "organization")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
        ("GUIOS", {"fields": ("first_name", "last_name", "role", "organization", "area")}),
    )


admin.site.register(PendingSignup)
