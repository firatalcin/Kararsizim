from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("anket/yeni/", views.poll_create, name="create"),
    path("anket/<int:pk>/", views.poll_detail, name="detail"),
    path("anket/<int:pk>/oy/", views.poll_vote, name="vote"),
    path("anket/<int:pk>/sil/", views.poll_delete, name="delete"),
]
