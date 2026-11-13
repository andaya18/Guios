from django.contrib import admin

from .models import Evaluation, EvaluationFactor, Software


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "license_type", "organization")
    list_filter = ("license_type", "organization")
    search_fields = ("name",)


class EvaluationFactorInline(admin.TabularInline):
    model = EvaluationFactor
    fields = (
        "factor", "decision_importance", "suggested_importance",
        "relative_importance", "scope", "is_relevant", "pm", "foda",
    )
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    """View-only: evaluations change through workflow.py, never from the admin (§5.2)."""

    list_display = ("software", "author", "organization", "status", "recommendation", "updated_at")
    list_filter = ("status", "recommendation", "catalog_version", "organization")
    search_fields = ("software__name", "author__email")
    inlines = [EvaluationFactorInline]
    actions = None  # delete_selected uses queryset.delete(), which skips the model guard

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is not None and not obj.is_finalized
