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
- **Local `.env` points at Supabase** (project `kararsizim-eu`, id `nlxgpagqfsuepdoyhrba`, session pooler :5432), so `runserver`, `migrate` and `shell` hit the shared Supabase database — clean up any test data you create there. `manage.py test` always uses SQLite regardless (see `config/settings.py`). The Supabase MCP (`execute_sql`, `get_advisors`, …) can inspect that project; run `get_advisors` (security) after new migrations.
- `.env` is gitignored and holds the DB password: never print it or echo `DATABASE_URL`.

## Architecture notes (not obvious from a single file)

- **Settings are env-driven** (`config/settings.py`). `manage.py` calls `load_dotenv()`; `config/wsgi.py` does not (Vercel injects env vars). With `DJANGO_DEBUG=False` and no `DJANGO_SECRET_KEY`, startup raises `ImproperlyConfigured` — so any `DEBUG=False` check needs a secret key set. Postgres-specific pooler options are applied only when `DATABASE_URL` resolves to the postgresql engine. Supabase tables all have RLS enabled with no policies (a DB event trigger enables it on new `public` tables), which blocks the Supabase Data API while Django, connecting as the table owner, is unaffected. WhiteNoise manifest storage is used only when `DEBUG=False`.
- **Custom user (`accounts.User`)**: login is by email (`USERNAME_FIELD="email"`). Email is lowercased both in `UserManager._create_user` and in `User.save()`; `UserManager.get_by_natural_key` matches email case-insensitively, which is what `authenticate(email=...)` relies on. Username format and reserved-name validators are defined on the model field, so ModelForms and the admin pick them up automatically; case-insensitive username uniqueness is a `Lower("username")` `UniqueConstraint` whose `violation_error_message` surfaces through `full_clean()`.
- **Polls**: `/` is the feed (`polls.views.feed`). Feed and detail both use `polls_with_counts()` (author + `total_votes` + per-option `vote_count` in constant queries) and render the shared `partials/_poll_card.html`; keep its explicit `order_by` — `annotate(Count)` makes Django drop `Meta.ordering`. The create form is `PollForm` + `OptionFormSet` (prefix `options`; blank rows ignored, 2–5 and duplicates checked in `BaseOptionFormSet.clean`), with `static/js/poll-form.js` adding/removing rows. Option colour comes from `Option.color` (position) and avatar colour from `User.avatar_color`.
- **Voting**: `POST /anket/<id>/oy/` (`polls.views.poll_vote`) → `services.cast_vote` (raises `InvalidOption` / `AlreadyVoted`; the DB unique constraints are the real double-vote guard). Members vote as `user`; anonymous visitors via the signed `kz_voter` cookie (`polls/voter.py`). JSON when `Accept: application/json`, otherwise messages + redirect. Card state (buttons vs results vs owner view) is set per poll by `views.prepare_cards()`, which also runs the single `get_user_votes` query; `_poll_card.html` + `_option_body.html` render it and `renderResults()` in `static/js/main.js` mirrors the results markup — change both together. After editing static JS/CSS, hard-refresh the browser (runserver doesn't cache-bust).
- **Templates**: project-level `templates/` (in `TEMPLATES["DIRS"]`). `base.html` includes `partials/_navbar.html` (auth-aware) and `partials/_messages.html` (Django messages as toasts; `window.kz.toast()` adds more from JS). Forms render field by field via `partials/_field.html` + `partials/_form_errors.html`. `base.html` also exposes the CSRF token via `<meta name="csrf-token">`; `static/js/main.js` reads it through `window.kz.csrfToken()`. `500.html` extends `base.html`, so the base template must not depend on context that is missing during a server error.
- **CSS**: single `static/css/main.css`, design tokens in `:root` at the top; option colours use `.chip--{violet,pink,orange,teal,sky}` with matching `-soft` backgrounds.
