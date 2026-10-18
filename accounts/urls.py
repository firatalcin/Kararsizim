from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.login, name="login"),
    path("cikis/", views.logout, name="logout"),
    path("hesap/sil/", views.delete_account, name="delete"),
    path("parola/sifirla/", views.password_reset, name="password_reset"),
    path(
        "parola/sifirla/gonderildi/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "parola/sifirla/tamam/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("parola/sifirla/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    # "tekrar" must come before the token route, which would otherwise swallow it.
    path("e-posta/dogrula/tekrar/", views.resend_verification, name="resend_verification"),
    path("e-posta/dogrula/<str:token>/", views.verify_email, name="verify_email"),
]
