from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import HttpResponse

from apps.catalog.models import Dimension, Factor


@login_required
def help_guide(request):
    """I01: the GUIOS guide, available to decisors and administrators (§3)."""
    dimensions = Dimension.objects.prefetch_related(
        Prefetch("factors", queryset=Factor.objects.order_by("order").prefetch_related("subfactors"))
    )
    return render(request, "core/help.html", {"dimensions": dimensions})


ADMIN_ONLY_TEXT = "Esta sección es solo para administradores."
GENERIC_DENIED_TEXT = "No tienes acceso a este contenido."


def _error_response(request, status, **copy):
    html = render_to_string("errors/error.html", {"error_code": status, **copy}, request=request)
    return HttpResponse(html, status=status)


def permission_denied(request, exception=None):
    """G03: shown whenever a user reaches something their role does not allow (§3)."""
    return _error_response(
        request,
        403,
        error_heading="Acceso restringido",
        error_title="No tienes permiso para ver esta página",
        error_text=(
            ADMIN_ONLY_TEXT if request.path.startswith("/gestion/") else GENERIC_DENIED_TEXT
        ) + " Si crees que es un error, contacta al administrador de tu organización.",
    )


def page_not_found(request, exception=None):
    """G03 variant: same design with the 404 copy."""
    return _error_response(
        request,
        404,
        error_heading="Página no encontrada",
        error_title="No encontramos esta página",
        error_text="Es posible que la dirección esté mal escrita o que la página ya no exista.",
    )
