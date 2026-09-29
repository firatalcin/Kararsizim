from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import BaseUserCreationForm

from .models import User


class RegisterForm(BaseUserCreationForm):
    """Sign-up form: username, email and password (twice).

    Username format and reserved names are validated by the model field's
    validators; case-insensitive uniqueness is checked here so the error lands
    on the username field instead of the non-field errors.
    """

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The base class autofocuses USERNAME_FIELD (email); the username comes first here.
        self.fields["email"].widget.attrs.pop("autofocus", None)

        username = self.fields["username"]
        username.widget.attrs.update(
            {"autofocus": True, "autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"}
        )

        email = self.fields["email"]
        email.required = True
        email.help_text = "E-postan kimseye gösterilmez."
        email.widget.attrs.update({"autocomplete": "email"})

        self.fields["password1"].help_text = "En az 8 karakter; çok yaygın ya da sadece rakamlardan oluşan bir parola olmasın."
        self.fields["password2"].label = "Parola (tekrar)"
        self.fields["password2"].help_text = ""

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı alınmış.", code="username_taken")
        return username

    def clean_email(self):
        # Lowercase before the model's unique check so "Ali@x.com" collides with "ali@x.com".
        return self.cleaned_data["email"].strip().lower()


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Parola",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "E-posta veya parola hatalı.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")
        if email and password:
            # ModelBackend maps the USERNAME_FIELD kwarg (email) to the lookup.
            self.user_cache = authenticate(self.request, email=email.strip().lower(), password=password)
            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")
        return self.cleaned_data

    def get_user(self):
        return self.user_cache
