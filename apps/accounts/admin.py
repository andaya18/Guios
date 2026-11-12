from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organization, PendingSignup, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "sector", "is_active")
    search_fields = ("name", "domain")


@admin.register(User)
class GuiosUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "role", "organization", "is_active")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (
        ("GUIOS", {"fields": ("role", "organization", "area")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("GUIOS", {"fields": ("email", "role", "organization", "area")}),
    )


admin.site.register(PendingSignup)
