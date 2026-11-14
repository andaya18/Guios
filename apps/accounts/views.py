from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.views.decorators.http import require_POST
from django.contrib.auth.views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from apps.evaluations.selectors import decisor_dashboard

from .forms import (
    ProfileForm,
    GuiosPasswordResetForm,
    GuiosSetPasswordForm,
    LoginForm,
    OrganizationForm,
    SignupForm,
    VerificationForm,
)
from .mail_status import mail_status
from .models import PendingSignup, User
from .services import (
    active_organization_for_email,
    create_pending_signup,
    email_domain,
    new_code,
    resend_pending_signup_code,
    send_verification_email,
    verify_pending_signup,
)


def home_url_for(user):
    return "/gestion/" if user.role == "administrador" else "/"


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("remember"):
            self.request.session.set_expiry(settings.REMEMBER_ME_AGE)
        else:
            # Cookie dies with the browser; the server still expires it after SESSION_COOKIE_AGE idle.
            self.request.session.set_expiry(0)
        return response

    def get_default_redirect_url(self):
        return home_url_for(self.request.user)


@login_required
def dashboard(request):
    if request.user.role == "administrador":
        return redirect("/gestion/")
    return render(request, "dashboard/decisor.html", {"summary": decisor_dashboard(request.user)})


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        pending = create_pending_signup(data["email"], data["first_name"], data["last_name"], data["password"])
        request.session["pending_signup_email"] = pending.email
        return redirect("accounts:signup_verify")
    return render(request, "accounts/signup.html", {"form": form})


def signup_verify(request):
    email = request.session.get("pending_signup_email")
    pending = PendingSignup.objects.filter(email=email).first() if email else None
    if pending is None:
        return redirect("accounts:signup")

    verification_form = VerificationForm()
    if request.method == "POST":
        if "resend" in request.POST:
            try:
                resend_pending_signup_code(pending)
            except ValueError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Te enviamos un nuevo código de verificación.")
            return redirect("accounts:signup_verify")

        verification_form = VerificationForm.from_boxes(request.POST)
        if verification_form.is_valid():
            try:
                user = verify_pending_signup(pending, verification_form.cleaned_data["code"])
            except ValueError as error:
                verification_form.add_error("code", str(error))
            else:
                request.session.pop("pending_signup_email", None)
                request.session["pending_user_id"] = user.pk
                return redirect("accounts:signup_organization")

    first_name, _, last_name = pending.name.partition("|")
    background_form = SignupForm(initial={"first_name": first_name, "last_name": last_name, "email": pending.email})
    return render(
        request,
        "accounts/signup.html",
        {"form": background_form, "verification_form": verification_form, "pending_email": pending.email},
    )


def _finish_signup(request, user, organization):
    user.organization = organization
    user.save(update_fields=["organization"])
    login(request, user)
    request.session.pop("pending_user_id", None)
    return redirect(home_url_for(user))


def signup_organization(request):
    user = get_object_or_404(User, pk=request.session.get("pending_user_id"), organization__isnull=True)
    domain = email_domain(user.email)
    organization = active_organization_for_email(user.email)
    if organization:
        return _finish_signup(request, user, organization)

    form = OrganizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        organization = form.save(commit=False)
        organization.domain = domain
        try:
            with transaction.atomic():
                organization.save()
        except IntegrityError:
            # Another user of the same domain registered it first: join the winner (§6.1).
            organization = active_organization_for_email(user.email)
        if organization is not None and organization.pk:
            return _finish_signup(request, user, organization)
        form.add_error(None, "No se pudo registrar la organización. Intenta de nuevo.")
    return render(request, "accounts/signup_organization.html", {"form": form, "domain": domain})


class AccountPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    form_class = GuiosPasswordResetForm
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class AccountPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_form.html"
    extra_context = {"form": GuiosPasswordResetForm(), "sent": True}


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = GuiosSetPasswordForm
    post_reset_login = True

    def get_success_url(self):
        return home_url_for(self.user)



@login_required
def profile(request):
    """Cuenta / Configuración: name, area and appearance; admins also see the mail status."""
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("accounts:profile")
    is_admin = request.user.role == "administrador"
    return render(request, "accounts/profile.html", {
        "form": form,
        "organization": request.user.organization,
        "mail": mail_status() if is_admin else None,
    })


@login_required
@require_POST
def send_test_email(request):
    """Sends the real verification email (same function as signup) so delivery can be checked."""
    if request.user.role != "administrador":
        raise PermissionDenied
    recipient = request.POST.get("recipient", "").strip() or request.user.email
    try:
        validate_email(recipient)
    except ValidationError:
        messages.error(request, "Escribe un correo válido para la prueba.")
        return redirect("accounts:profile")
    try:
        send_verification_email(recipient, new_code())
    except Exception as error:  # SMTP errors vary by provider; show the reason to the admin.
        messages.error(request, f"No se pudo enviar el correo de prueba: {error}")
        return redirect("accounts:profile")
    if mail_status()["is_real"]:
        messages.success(request, f"Correo de prueba enviado a {recipient}. Revisa también la carpeta de spam.")
    else:
        messages.warning(request, "Modo consola: el correo se imprimió en la terminal del servidor y no salió a internet.")
    return redirect("accounts:profile")
