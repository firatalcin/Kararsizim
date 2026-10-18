from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("gizlilik/", TemplateView.as_view(template_name="privacy.html"), name="privacy"),
    path("", include("accounts.urls")),
    path("", include("polls.urls")),
]
