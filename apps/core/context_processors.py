"""Data every authenticated page shell needs (sidebar user card, top bar subtitle, history badge)."""


def organization_label(user):
    """'UNEMI – Dirección TIC' when the user has an area, otherwise only the organization (§7.1)."""
    if user.role == "administrador" or user.organization_id is None:
        return "Administración"
    name = user.organization.name
    return f"{name} – {user.area}" if user.area else name


def history_badge(user):
    """Finished evaluations of the organization plus the user's own drafts (§7.1)."""
    from apps.evaluations.selectors import history_count  # local import: evaluations depends on core

    return history_count(user)


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"shell_base": "base/public.html", "shell_home": "/acceso/"}
    is_admin = user.role == "administrador"
    return {
        "shell_base": "base_admin.html" if is_admin else "base_decisor.html",
        "shell_home": "/gestion/" if is_admin else "/",
        "shell_organization": organization_label(user),
        "shell_role": user.get_role_display(),
        "shell_history_badge": history_badge(user) if user.role == "decisor" else 0,
    }
