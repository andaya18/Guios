from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("nueva/", views.new_evaluation, name="new"),
    path("<int:pk>/etapa-1/", views.stage1, name="stage1"),
    path("<int:pk>/etapa-2/", views.stage2, name="stage2"),
    path("<int:pk>/etapa-3/", views.stage3, name="stage3"),
    path("<int:pk>/finalizar/", views.finish, name="finish"),
    path("<int:pk>/factor/<int:factor_id>/", views.save_factor, name="factor"),
    path("<int:pk>/respuesta/<int:answer_id>/", views.save_answer, name="answer"),
]
