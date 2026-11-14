from django.urls import path

from apps.exports.views import export_evaluation

from . import history_views

app_name = "history"

urlpatterns = [
    path("", history_views.history_list, name="list"),
    path("<int:pk>/", history_views.history_detail, name="detail"),
    path("<int:pk>/duplicar/", history_views.duplicate, name="duplicate"),
    path("<int:pk>/eliminar/", history_views.delete_draft, name="delete"),
    path("<int:pk>/exportar/", export_evaluation, name="export"),
]
