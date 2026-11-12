from django.contrib import admin

from .models import CatalogVersion, Dimension, Factor, FactorVersion, Subfactor


class FactorVersionInline(admin.TabularInline):
    model = FactorVersion
    extra = 0


class SubfactorInline(admin.TabularInline):
    model = Subfactor
    extra = 0


@admin.register(CatalogVersion)
class CatalogVersionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "status", "published_at")
    list_filter = ("status",)
    inlines = [FactorVersionInline]


@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Factor)
class FactorAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "dimension")
    list_filter = ("dimension",)
    search_fields = ("name",)
    inlines = [SubfactorInline]


@admin.register(Subfactor)
class SubfactorAdmin(admin.ModelAdmin):
    list_display = ("name", "factor", "order")
    list_filter = ("factor",)
    search_fields = ("name",)


@admin.register(FactorVersion)
class FactorVersionAdmin(admin.ModelAdmin):
    list_display = ("version", "factor", "suggested_importance", "default_scope")
    list_filter = ("version", "default_scope")
