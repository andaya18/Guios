from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse


def role_required(role):
    """Login plus role check (§3). HTMX calls get 401 so the page can show 'Tu sesión expiró' (G02)."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get("HX-Request"):
                    return HttpResponse(status=401)
                return redirect_to_login(request.get_full_path())
            if request.user.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


decisor_required = role_required("decisor")
