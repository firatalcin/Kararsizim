# Kararsızım

Kararsız kaldığın konularda hızlıca anket aç, herkes oy versin.
Django 5.2 + saf HTML/CSS/JS. Proje planı: [docs/PROJECT.md](docs/PROJECT.md).

## Yerel kurulum

Gereken: Python 3.14.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`DATABASE_URL` tanımlı değilse yerel SQLite (`db.sqlite3`) kullanılır.

## Testler

```bash
python manage.py check
python manage.py test
```
