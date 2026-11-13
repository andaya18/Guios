from django.contrib import admin
from django.urls import include, path

from apps.core.views import help_guide


urlpatterns = [
    path("admin/", admin.site.urls),
    path("ayuda/", help_guide, name="help"),
    path("gestion/", include("apps.management.urls")),
    path("", include("apps.accounts.urls")),
]

handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
