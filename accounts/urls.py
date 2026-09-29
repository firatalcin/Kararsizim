from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.login, name="login"),
    path("cikis/", views.logout, name="logout"),
]
