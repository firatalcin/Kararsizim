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
- `DJANGO_DEBUG` defaults to **False** (only `manage.py test` defaults to True), so every other command needs `DJANGO_DEBUG=True` in `.env` (it is in `.env.example`) or the environment, or it fails asking for `DJANGO_SECRET_KEY`.
- `.claude/launch.json` defines a `django` preview server on port 8000 for the in-app browser. On a Mac its Windows interpreter path does not exist, and the preview launcher cannot start processes under `~/Desktop` (`Operation not permitted`): start `runserver` through Bash with the needed env vars (`DJANGO_DEBUG=True`, a scratch `DATABASE_URL`) and open it with `preview_start {url: "http://localhost:<port>/"}`.
- To try management commands against a throwaway DB, set `DATABASE_URL=sqlite:///<scratch path>` for that command.
- **Local `.env` points at Supabase** (project `kararsizim-eu`, id `nlxgpagqfsuepdoyhrba`, session pooler :5432), so `runserver`, `migrate` and `shell` hit the shared Supabase database — clean up any test data you create there. `manage.py test` always uses SQLite regardless (see `config/settings.py`). The Supabase MCP (`execute_sql`, `get_advisors`, …) can inspect that project; run `get_advisors` (security) after new migrations.
- `.env` is gitignored and holds the DB password: never print it or echo `DATABASE_URL`.

## Architecture notes (not obvious from a single file)

- **Settings are env-driven** (`config/settings.py`). `manage.py` calls `load_dotenv()`; `config/wsgi.py` does not (Vercel injects env vars). `DEBUG` fails closed (default False; `DEBUG=True` with the `VERCEL` env var raises). With `DJANGO_DEBUG=False` and no `DJANGO_SECRET_KEY`, startup raises `ImproperlyConfigured` — so any `DEBUG=False` check needs a secret key set. Settings tests (`config/tests.py`) import the settings in a subprocess with a controlled env, because settings are read at import time. Postgres-specific pooler options are applied only when `DATABASE_URL` resolves to the postgresql engine. Supabase tables all have RLS enabled with no policies (a DB event trigger enables it on new `public` tables), which blocks the Supabase Data API while Django, connecting as the table owner, is unaffected. WhiteNoise manifest storage is used only when `DEBUG=False`.
- **Custom user (`accounts.User`)**: login is by email (`USERNAME_FIELD="email"`). Email is lowercased both in `UserManager._create_user` and in `User.save()`; `UserManager.get_by_natural_key` matches email case-insensitively, which is what `authenticate(email=...)` relies on. Username format and reserved-name validators are defined on the model field, so ModelForms and the admin pick them up automatically; case-insensitive username uniqueness is a `Lower("username")` `UniqueConstraint` whose `violation_error_message` surfaces through `full_clean()`.
- **Polls**: `/` is the feed (`polls.views.feed`). Feed and detail both use `polls_with_counts()` (author + `total_votes` + per-option `vote_count` in constant queries) and render the shared `partials/_poll_card.html`; keep its explicit `order_by` — `annotate(Count)` makes Django drop `Meta.ordering`. The create form is `PollForm` + `OptionFormSet` (prefix `options`; blank rows ignored, 2–5 and duplicates checked in `BaseOptionFormSet.clean`), with `static/js/poll-form.js` adding/removing rows. Option colour comes from `Option.color` (position) and avatar colour from `User.avatar_color`.
- **Voting**: `POST /anket/<id>/oy/` (`polls.views.poll_vote`) → `services.cast_vote` (raises `InvalidOption` / `AlreadyVoted`; the DB unique constraints are the real double-vote guard). Members vote as `user`; anonymous visitors via the signed `kz_voter` cookie (`polls/voter.py`). JSON when `Accept: application/json`, otherwise messages + redirect. Card state (buttons vs results vs owner view) is set per poll by `views.prepare_cards()`, which also runs the single `get_user_votes` query; `_poll_card.html` + `_option_body.html` render it and `renderResults()` in `static/js/main.js` mirrors the results markup — change both together. After editing static JS/CSS, hard-refresh the browser (runserver doesn't cache-bust).
- **Vote identity**: anonymous visitors receive the `kz_voter` cookie when feed/detail/profile render (`voter.ensure_voter_cookie`), not when they vote, so racing first votes share a token. A member's vote also counts the anonymous vote cast from the same browser (`cast_vote(browser_token=…)`, `get_user_votes`). Percentages are only computed/rendered when `poll.show_results` — never leak them into the HTML of someone who may not see results.
- **Rate limiting** (`core/throttle.py`): `@throttle_post(scope, ident=…)` counts POSTs in `ThrottleBucket` (atomic fixed-window counters, HMAC'd keys, no IP/e-mail stored); limits live in `settings.THROTTLE_LIMITS`; per-view stacking is used for login (IP + e-mail). `THROTTLE_ENABLED` is off in tests — tests that exercise it use `override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=…)`. `purge_expired()` also deletes expired sessions. The admin login is wrapped in `accounts/admin.py`.
- **Security headers**: `config/middleware.py` adds CSP (`script-src 'self'`, no inline scripts or event handlers anywhere; `style-src` allows inline styles and Google Fonts) and `Permissions-Policy`, except under `/admin/`.
- **E-mail features** (password reset, address verification, `User.email_verified`) are on only when `settings.EMAIL_FEATURES_ENABLED` (SMTP configured, or `DJANGO_EMAIL_ENABLED=True` locally with the console backend); templates see it as `email_features_enabled` via `accounts.context_processors.site`. Tests turn it on with `override_settings`. Unverified members can vote but not open polls while it is on.
- **Poll text** goes through `polls/text.py` (`clean_text`, `has_visible_text`, `fold_key`) in the forms; keep ZWJ/ZWNJ (emoji sequences) when changing the invisible-character list.
- **Migrations**: the schema may be applied to Supabase before the new code is deployed, so the old release must keep working against it: give new `NOT NULL` columns a `db_default` (see `User.email_verified` and `accounts.tests.SchemaCompatibilityTests`). `core.0002` revokes `anon`/`authenticated` table grants on Supabase (Postgres with those roles only; no-op on SQLite). New tables created later get no Data API grants either.
- **Profile** `/u/<username>/` lives in `polls.views.profile` (case-insensitive lookup; reuses `polls_with_counts` + `prepare_cards` + `partials/_pagination.html`) to avoid an `accounts.views` ↔ `polls.views` import cycle. Cards link authors there and include a `data-copy-link` anchor handled in `main.js`.
- The site sends `X-Frame-Options: DENY`, so pages can't be audited inside iframes; for a11y checks load axe-core into the page itself.
- **Templates**: project-level `templates/` (in `TEMPLATES["DIRS"]`). `base.html` includes `partials/_navbar.html` (auth-aware) and `partials/_messages.html` (Django messages as toasts; `window.kz.toast()` adds more from JS). Forms render field by field via `partials/_field.html` + `partials/_form_errors.html`. `base.html` also exposes the CSRF token via `<meta name="csrf-token">`; `static/js/main.js` reads it through `window.kz.csrfToken()`. `500.html` extends `base.html`, so the base template must not depend on context that is missing during a server error.
- **CSS**: single `static/css/main.css`, design tokens in `:root` at the top; option colours use `.chip--{violet,pink,orange,teal,sky}` with matching `-soft` backgrounds.
