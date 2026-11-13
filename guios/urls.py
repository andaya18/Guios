from django.contrib import admin
from django.urls import include, path

from apps.core.views import help_guide
from apps.evaluations.history_views import compare


urlpatterns = [
    path("admin/", admin.site.urls),
    path("ayuda/", help_guide, name="help"),
    path("gestion/", include("apps.management.urls")),
    path("evaluaciones/", include("apps.evaluations.urls")),
    path("historial/", include("apps.evaluations.urls_history")),
    path("comparar/", compare, name="compare"),
    path("", include("apps.accounts.urls")),
]

handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
