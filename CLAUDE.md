# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The full product spec, phase plan, working rules and progress log live in `docs/PROJECT.md` (imported below). It is the single source of truth: work phase by phase, update its "İlerleme Durumu" / "Notlar" sections when a phase ends, and ask before changing any decision written there.

@docs/PROJECT.md

## Commands

Windows machine; there is no global Python on PATH, so call the venv interpreter directly (Python 3.14):

```bash
.venv/Scripts/python.exe manage.py runserver          # http://localhost:8000
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py test               # all tests
.venv/Scripts/python.exe manage.py test accounts      # one app
.venv/Scripts/python.exe manage.py test accounts.tests.UserModelTests.test_email_is_lowercased  # one test
.venv/Scripts/python.exe manage.py makemigrations && .venv/Scripts/python.exe manage.py migrate
```

- No linter/formatter is configured. Git repo on `main`; commit only when the user asks.
- `.claude/launch.json` defines a `django` preview server on port 8000 for the in-app browser.
- To try management commands against a throwaway DB, set `DATABASE_URL=sqlite:///<scratch path>` for that command.

## Architecture notes (not obvious from a single file)

- **Settings are env-driven** (`config/settings.py`). `manage.py` calls `load_dotenv()`; `config/wsgi.py` does not (Vercel injects env vars). With `DJANGO_DEBUG=False` and no `DJANGO_SECRET_KEY`, startup raises `ImproperlyConfigured` — so any `DEBUG=False` check needs a secret key set. Postgres-specific pooler options are applied only when `DATABASE_URL` resolves to the postgresql engine. WhiteNoise manifest storage is used only when `DEBUG=False`.
- **Custom user (`accounts.User`)**: login is by email (`USERNAME_FIELD="email"`). Email is lowercased both in `UserManager._create_user` and in `User.save()`; `UserManager.get_by_natural_key` matches email case-insensitively, which is what `authenticate(email=...)` relies on. Username format and reserved-name validators are defined on the model field, so ModelForms and the admin pick them up automatically; case-insensitive username uniqueness is a `Lower("username")` `UniqueConstraint` whose `violation_error_message` surfaces through `full_clean()`.
- **Temporary home page**: `/` is `polls.views.home` rendering `templates/polls/home.html` until the Phase 2 feed replaces it. Project URLs include `polls.urls` at the root.
- **Templates**: project-level `templates/` (in `TEMPLATES["DIRS"]`). `base.html` includes `partials/_navbar.html` and `partials/_messages.html` (placeholders to be filled in Phase 1) and exposes the CSRF token via `<meta name="csrf-token">`; `static/js/main.js` reads it through `window.kz.csrfToken()`. `500.html` extends `base.html`, so the base template must not depend on context that is missing during a server error.
- **CSS**: single `static/css/main.css`, design tokens in `:root` at the top; option colours use `.chip--{violet,pink,orange,teal,sky}` with matching `-soft` backgrounds.
