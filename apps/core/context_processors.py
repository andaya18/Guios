"""Data every authenticated page shell needs (sidebar user card, top bar subtitle, history badge)."""


def organization_label(user):
    """'UNEMI – Dirección TIC' when the user has an area, otherwise only the organization (§7.1)."""
    if user.role == "administrador" or user.organization_id is None:
        return "Administración"
    name = user.organization.name
    return f"{name} – {user.area}" if user.area else name


def history_badge(user):
    """Finished evaluations of the organization plus the user's own drafts (§7.1)."""
    try:
        from apps.evaluations.selectors import history_count
    except ImportError:
        return 0
    return history_count(user)


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "shell_organization": organization_label(user),
        "shell_role": user.get_role_display(),
        "shell_history_badge": history_badge(user) if user.role == "decisor" else 0,
    }
