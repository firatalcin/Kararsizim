from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import EmailLoginForm, RegisterForm


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


def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Hoş geldin @{user.username}! 🎉")
            return redirect(get_safe_next_url(request) or "/")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form, "next": get_safe_next_url(request)})


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
