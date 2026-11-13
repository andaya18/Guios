"""Vistas del área de administración. Las reglas viven en services.py y selectors.py."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import Organization, User
from apps.catalog.models import CatalogVersion, Dimension, Factor

from . import selectors, services
from .forms import FactorValuesForm, OrganizationForm, PublishForm, UserForm
from .permissions import AdministratorRequiredMixin


def tab_items(request, param, options, current, base):
    """Enlaces de las pestañas segmentadas que conservan el resto de los filtros."""
    items = []
    for value, label in options:
        query = request.GET.copy()
        query[param] = value
        query.pop("page", None)
        items.append((f"{base}?{query.urlencode()}", label, value == current))
    return items


class DashboardView(AdministratorRequiredMixin, TemplateView):
    template_name = "management/dashboard.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(summary=selectors.admin_dashboard(), **kwargs)


# Usuarios (U01 / U02)

class UserListView(AdministratorRequiredMixin, View):
    def get(self, request):
        params = request.GET
        tab = params.get("estado") if params.get("estado") in selectors.USER_TABS else "activos"
        counts = selectors.user_tab_counts()
        return render(request, "management/users/list.html", {
            "users": selectors.filter_users(
                tab=tab,
                query=params.get("q", "").strip(),
                role=params.get("rol", ""),
                organization=params.get("organizacion", ""),
            ),
            "tabs": tab_items(request, "estado", [
                (key, f"{label} · {counts[key]}")
                for key, label in (("activos", "Activos"), ("desactivados", "Desactivados"))
            ], tab, reverse("management:users")),
            "roles": User.ROLES,
            "organizations": Organization.objects.order_by("name"),
            "filters": params,
        })


class UserFormView(AdministratorRequiredMixin, View):
    template_name = "management/users/form.html"

    def get_user(self, pk):
        return get_object_or_404(User, pk=pk) if pk else None

    def get(self, request, pk=None):
        return render(request, self.template_name, {"form": UserForm(instance=self.get_user(pk))})

    def post(self, request, pk=None):
        form = UserForm(request.POST, instance=self.get_user(pk))
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        user = form.save()
        messages.success(request, f"Usuario {user.email} guardado.")
        return redirect("management:users")


# Organizaciones (O01 / O02)

class OrganizationListView(AdministratorRequiredMixin, View):
    template_name = "management/organizations/list.html"

    def list_context(self, request):
        params = request.GET
        tab = params.get("estado") if params.get("estado") in selectors.ORGANIZATION_TABS else "todas"
        counts = selectors.organization_tab_counts()
        return {
            "organizations": selectors.filter_organizations(
                tab=tab, query=params.get("q", "").strip(), sector=params.get("sector", "")
            ),
            "tabs": tab_items(request, "estado", [
                (key, f"{label} · {counts[key]}")
                for key, label in (("todas", "Todas"), ("activas", "Activas"), ("inactivas", "Inactivas"))
            ], tab, reverse("management:organizations")),
            "sectors": Organization.SECTORS,
            "filters": params,
        }

    def get(self, request):
        return render(request, self.template_name, self.list_context(request))


class OrganizationFormView(OrganizationListView):
    """O02 se muestra como modal sobre el listado O01, igual que en Figma."""

    def get_organization(self, pk):
        return get_object_or_404(Organization, pk=pk) if pk else None

    def render_modal(self, request, form):
        return render(request, self.template_name, {**self.list_context(request), "form": form})

    def get(self, request, pk=None):
        return self.render_modal(request, OrganizationForm(instance=self.get_organization(pk)))

    def post(self, request, pk=None):
        form = OrganizationForm(request.POST, instance=self.get_organization(pk))
        if not form.is_valid():
            return self.render_modal(request, form)
        organization = form.save()
        messages.success(request, f"Organización {organization.name} guardada.")
        return redirect("management:organizations")


class OrganizationReactivateView(AdministratorRequiredMixin, View):
    def post(self, request, pk):
        organization = get_object_or_404(Organization, pk=pk)
        organization.is_active = True
        organization.save(update_fields=["is_active"])
        messages.success(request, f"Organización {organization.name} reactivada.")
        return redirect("management:organizations")


# Catálogo (M01 a M03)

def get_version(number):
    return get_object_or_404(CatalogVersion, number=number)


def catalog_url():
    """El enlace Catálogo abre el borrador si existe; si no, la versión activa."""
    version = services.draft_version() or services.active_version()
    return reverse("management:catalog_editor", args=[version.number]) if version else reverse("management:catalog")


class VersionListView(AdministratorRequiredMixin, View):
    """M03: versiones con su estado y los cambios entre dos versiones."""

    def get(self, request):
        return self.render_page(request, *self.default_pair())

    def default_pair(self):
        active = services.active_version()
        return (services.previous_version(active) if active else None), active

    def render_page(self, request, base, other):
        return render(request, "management/catalog/versions.html", {
            "versions": selectors.versions_overview(),
            "base": base,
            "other": other,
            "changes": services.compare_versions(base, other) if base and other else [],
            "draft": services.draft_version(),
            "catalog_url": catalog_url(),
            **selectors.catalog_counts(),
        })


class VersionCompareView(VersionListView):
    def get(self, request):
        numbers = [request.GET.get("a", ""), request.GET.get("b", "")]
        if not all(number.isdigit() for number in numbers):
            raise Http404("Versión no encontrada.")
        return self.render_page(request, *(get_version(int(number)) for number in numbers))


class VersionActivateView(AdministratorRequiredMixin, View):
    def post(self, request, number):
        version = get_version(number)
        try:
            services.set_active_version(version)
        except services.CatalogRuleError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"La versión v{version.number} es ahora la activa.")
        return redirect("management:catalog")


class DraftCreateView(AdministratorRequiredMixin, View):
    def post(self, request):
        draft = services.create_draft()
        return redirect("management:catalog_editor", number=draft.number)


class CatalogEditorView(AdministratorRequiredMixin, View):
    """M01: árbol de factores y edición de IS y alcance de un borrador."""

    template_name = "management/catalog/editor.html"

    def selected_factor(self, request):
        factor_id = request.GET.get("factor", "")
        if factor_id.isdigit():
            return get_object_or_404(Factor.objects.select_related("dimension"), pk=int(factor_id))
        return Factor.objects.select_related("dimension").order_by("order").first()

    def get(self, request, number):
        version = get_version(number)
        factor = self.selected_factor(request)
        value = version.factor_values.get(factor=factor)
        form = FactorValuesForm(initial={
            "suggested_importance": value.suggested_importance,
            "default_scope": value.default_scope,
        })
        if version.status != "borrador":
            for field in form.fields.values():
                field.disabled = True
        return render(request, self.template_name, self.context(version, factor, form))

    def post(self, request, number):
        version = get_version(number)
        if version.status != "borrador":
            raise PermissionDenied("Solo se puede editar una versión en borrador.")
        factor = self.selected_factor(request)
        form = FactorValuesForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self.context(version, factor, form))
        services.update_draft_factor(
            version, factor, form.cleaned_data["suggested_importance"], form.cleaned_data["default_scope"]
        )
        messages.success(request, f"{factor.name} guardado en el borrador.")
        return redirect(f"{reverse('management:catalog_editor', args=[number])}?factor={factor.pk}")

    def context(self, version, factor, form):
        active = services.active_version()
        changes = services.compare_versions(active, version) if active and version != active else []
        changed_factor_ids = {change.factor.pk for change in changes}
        active_value = active.factor_values.get(factor=factor) if active else None
        return {
            "version": version,
            "active": active,
            "factor": factor,
            "form": form,
            "factor_subfactors": factor.subfactors.all(),
            "dimension_tree": Dimension.objects.prefetch_related("factors__subfactors"),
            "changes": changes,
            "changed_factor_ids": changed_factor_ids,
            "factor_changes": [change for change in changes if change.factor == factor],
            "active_value": active_value,
            "catalog_url": catalog_url(),
            **selectors.catalog_counts(),
        }


class PublishView(AdministratorRequiredMixin, View):
    """M02: cambios frente a la activa, sustento y autorización obligatorios."""

    template_name = "management/catalog/publish.html"

    def get_draft(self, number):
        version = get_version(number)
        if version.status != "borrador":
            raise PermissionDenied("Solo se puede publicar una versión en borrador.")
        return version

    def render_page(self, request, version, form):
        active = services.active_version()
        return render(request, self.template_name, {
            "version": version,
            "active": active,
            "changes": services.draft_changes(version),
            "before_label": f"Valor actual (v{active.number})" if active else "Valor actual",
            "form": form,
        })

    def get(self, request, number):
        version = self.get_draft(number)
        return self.render_page(request, version, PublishForm())

    def post(self, request, number):
        version = self.get_draft(number)
        form = PublishForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, version, form)
        services.publish_version(version, **{
            key: form.cleaned_data[key] for key in ("justification", "authorized_by", "name")
        })
        messages.success(request, f"Versión v{version.number} publicada. Las evaluaciones nuevas la usarán.")
        return redirect("management:catalog")
