from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

ADMINISTRATOR = "administrador"


def is_administrator(user):
    return user.is_authenticated and user.role == ADMINISTRATOR


class AdministratorRequiredMixin(LoginRequiredMixin):
    """Toda vista de /gestion/: visitantes al inicio de sesión, decisores a la pantalla 403 (§3)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_administrator(request.user):
            raise PermissionDenied("Esta sección es solo para administradores.")
        return super().dispatch(request, *args, **kwargs)
