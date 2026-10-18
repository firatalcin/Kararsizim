from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from core.throttle import throttle_post

from .models import User

# Staff login is the most valuable brute-force target: give it the same rate limit as the site login.
admin.site.login = throttle_post("admin-login")(admin.site.login)


class UserCreationAdminForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username")


class UserChangeAdminForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm

    list_display = ("username", "email", "email_verified", "is_staff", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "email_verified", "username", "password")}),
        ("Yetkiler", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Tarihler", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "usable_password", "password1", "password2"),
        }),
    )
