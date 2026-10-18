import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.throttle import hit, throttle_post, too_many_requests

from .emails import read_verification_token, send_verification_email
from .forms import DeleteAccountForm, EmailLoginForm, RegisterForm

logger = logging.getLogger(__name__)


def get_safe_next_url(request):
    """Return the ?next= target if it points to this site, otherwise None."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def email_ident(request):
    """Rate-limit identifier for per-account limits: the submitted e-mail (None if blank)."""
    return (request.POST.get("email") or "").strip().lower() or None


def send_verification_safely(request, user):
    """Send the verification mail; a broken mail server must never block signing up."""
    try:
        send_verification_email(request, user)
    except Exception:
        logger.exception("Verification e-mail for user %s could not be sent", user.pk)
        return False
    return True


@throttle_post("register")
def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                # Someone took the username/e-mail between the form's check and the INSERT.
                form.add_error(None, "Bu kullanıcı adı veya e-posta az önce başkası tarafından alındı. Başka bir tane dene.")
            else:
                auth_login(request, user)
                messages.success(request, f"Hoş geldin @{user.username}! 🎉")
                if settings.EMAIL_FEATURES_ENABLED:
                    if send_verification_safely(request, user):
                        messages.info(request, "E-postana bir doğrulama bağlantısı gönderdik.")
                    else:
                        messages.warning(request, "Doğrulama e-postası gönderilemedi. Sayfanın üstünden tekrar isteyebilirsin.")
                return redirect(get_safe_next_url(request) or "/")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form, "next": get_safe_next_url(request)})


@throttle_post("login")
@throttle_post("login-email", ident=email_ident)
def login(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f"Tekrar hoş geldin @{user.username}! 👋")
            return redirect(get_safe_next_url(request) or "/")
    else:
        form = EmailLoginForm(request)

    return render(request, "accounts/login.html", {"form": form, "next": get_safe_next_url(request)})


@require_POST
def logout(request):
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, "Çıkış yaptın. Görüşürüz! 👋")
    return redirect("/")


@login_required
@throttle_post("account-delete", ident=lambda request: f"user:{request.user.pk}")
def delete_account(request):
    """Self-service erasure: the account, its polls and its votes go (Poll/Vote cascade)."""
    if request.method == "POST":
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            auth_logout(request)
            user.delete()
            messages.success(request, "Hesabın ve tüm verilerin silindi. Görüşürüz! 👋")
            return redirect("/")
    else:
        form = DeleteAccountForm(request.user)
    return render(request, "accounts/delete_account.html", {"form": form})


# ---------- E-mail verification ----------


def verify_email(request, token):
    if not settings.EMAIL_FEATURES_ENABLED:
        raise Http404
    user = read_verification_token(token)
    if user is None:
        messages.error(request, "Doğrulama bağlantısı geçersiz ya da süresi dolmuş.")
    else:
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        messages.success(request, "E-postan doğrulandı. Teşekkürler! ✅")
    return redirect("/")


@login_required
@require_POST
@throttle_post("verify-mail", ident=lambda request: f"user:{request.user.pk}")
def resend_verification(request):
    if not settings.EMAIL_FEATURES_ENABLED:
        raise Http404
    if request.user.email_verified:
        messages.info(request, "E-postan zaten doğrulanmış.")
    elif send_verification_safely(request, request.user):
        messages.success(request, "Doğrulama e-postasını gönderdik. Gelen kutunu kontrol et.")
    else:
        messages.error(request, "E-posta şu an gönderilemedi. Biraz sonra tekrar dene.")
    return redirect(get_safe_next_url(request) or "/")


# ---------- Password reset (Django's views, Turkish templates) ----------


class PasswordResetRequestView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def dispatch(self, request, *args, **kwargs):
        if not settings.EMAIL_FEATURES_ENABLED:
            messages.info(request, "Parola sıfırlama şu an kullanılamıyor.")
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Keeps anyone from filling a victim's inbox with reset mails.
        allowed, retry_after = hit("password-reset-email", form.cleaned_data["email"].strip().lower())
        if not allowed:
            return too_many_requests(self.request, retry_after)
        try:
            return super().form_valid(form)
        except Exception:
            # Same answer as success, so a failure doesn't reveal which addresses have accounts.
            logger.exception("Password reset e-mail could not be sent")
            return redirect(self.success_url)


password_reset = throttle_post("password-reset")(PasswordResetRequestView.as_view())


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        if not user.email_verified:  # reading the reset mail proves the address is theirs
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return response
