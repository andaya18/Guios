from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Organization(models.Model):
    SECTORS = [("publico", "Público"), ("privado", "Privado")]

    name = models.CharField(max_length=150)
    domain = models.CharField(max_length=120, unique=True)
    sector = models.CharField(max_length=10, choices=SECTORS)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GuiosUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "administrador")
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("El superusuario debe tener permisos administrativos.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLES = [("decisor", "Decisor"), ("administrador", "Administrador")]

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=15, choices=ROLES, default="decisor")
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    area = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = GuiosUserManager()

    def __str__(self):
        return self.email


class PendingSignup(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    password_hash = models.CharField(max_length=255)
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.email
