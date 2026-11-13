from apps.accounts.models import Organization, User

PASSWORD = "Correcta123!"


def make_organization(name="UNEMI", domain="unemi.edu.ec", sector="publico", **extra):
    return Organization.objects.create(name=name, domain=domain, sector=sector, **extra)


def make_admin(email="admin@guios.ec", **extra):
    extra.setdefault("first_name", "Carlos")
    extra.setdefault("last_name", "Mora")
    return User.objects.create_user(email=email, password=PASSWORD, role="administrador", **extra)


def make_decisor(organization, email="ana@unemi.edu.ec", **extra):
    extra.setdefault("first_name", "Ana")
    extra.setdefault("last_name", "Ruiz")
    return User.objects.create_user(
        email=email, password=PASSWORD, role="decisor", organization=organization, **extra
    )
