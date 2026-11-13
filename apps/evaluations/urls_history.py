from django.urls import path

from . import history_views

app_name = "history"

urlpatterns = [
    path("<int:pk>/eliminar/", history_views.delete_draft, name="delete"),
]
