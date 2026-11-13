from django.urls import path

from . import views

app_name = "management"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("usuarios/", views.UserListView.as_view(), name="users"),
    path("usuarios/nuevo/", views.UserFormView.as_view(), name="user_create"),
    path("usuarios/<int:pk>/", views.UserFormView.as_view(), name="user_edit"),
    path("organizaciones/", views.OrganizationListView.as_view(), name="organizations"),
    path("organizaciones/nueva/", views.OrganizationFormView.as_view(), name="organization_create"),
    path("organizaciones/<int:pk>/", views.OrganizationFormView.as_view(), name="organization_edit"),
    path(
        "organizaciones/<int:pk>/reactivar/",
        views.OrganizationReactivateView.as_view(),
        name="organization_reactivate",
    ),
    path("catalogo/", views.VersionListView.as_view(), name="catalog"),
    path("catalogo/comparar/", views.VersionCompareView.as_view(), name="catalog_compare"),
    path("catalogo/nueva/", views.DraftCreateView.as_view(), name="catalog_draft_create"),
    path("catalogo/<int:number>/", views.CatalogEditorView.as_view(), name="catalog_editor"),
    path("catalogo/<int:number>/activar/", views.VersionActivateView.as_view(), name="catalog_activate"),
    path("catalogo/<int:number>/publicar/", views.PublishView.as_view(), name="catalog_publish"),
]
