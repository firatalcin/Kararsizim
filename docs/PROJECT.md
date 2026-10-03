# Kararsızım — Proje Planı ve Claude Code Talimatları

> Bu dosya projenin tek referans kaynağıdır. Claude Code bu dosyayı her oturumda okur.
> Proje **fazlar halinde** geliştirilir. Aynı anda yalnızca istenen faz uygulanır.

---

## 0. Bu dosya nasıl kullanılır?

Kullanıcı her seferinde tek bir faz ister, örneğin:

- `CLAUDE.md'deki Faz 0'ı uygula.`
- `Faz 2'yi uygula, bitince test et ve özetle.`

### Claude Code için çalışma kuralları

1. **Sadece istenen fazı uygula.** Sonraki fazların işine başlama; gerekiyorsa sadece not düş.
2. Faza başlamadan önce o fazın "Yapılacaklar" ve "Kabul kriterleri" bölümlerini oku, kısa bir plan çıkar.
3. Faz bitince:
   - `python manage.py check` ve `python manage.py test` çalıştır, hepsi geçmeli.
   - Bu dosyanın en altındaki **İlerleme Durumu** bölümünde ilgili fazı `[x]` yap ve tarih ekle.
   - Kullanıcıya kısa bir özet ver: ne yapıldı, nasıl denenir, bilinen eksikler.
4. Bu dosyada yazan bir kararı değiştirmek gerekiyorsa önce kullanıcıya sor.
5. Basit tut. Bu bir **prototip**. Ek kütüphane eklemeden önce gerçekten gerekli mi diye düşün; "Bağımlılıklar" listesinde olmayan bir paket eklemek için kullanıcıya sor.
6. Kod (değişken, fonksiyon, model adları, yorumlar) **İngilizce**; kullanıcıya görünen tüm metinler (arayüz, hata mesajları, URL yolları) **Türkçe**.
7. Gizli bilgileri (SECRET_KEY, veritabanı parolası) asla koda veya git'e yazma; `.env` kullan.

---

## 1. Ürün özeti

**Kararsızım**, kullanıcıların kararsız kaldıkları konularda diğer kullanıcılara danışmak için hızlıca anket açtığı bir web uygulamasıdır.

Örnek: *"Bugün sinemaya mı gitsem, restorana mı?"* → 2–5 seçenek → herkes oy verir → sonuç yüzdelerle görünür.

### Temel kurallar

| Konu | Kural |
|---|---|
| Takip sistemi | **Yok.** Herkes platformdaki tüm anketleri görür. |
| Anket görüntüleme | Üye olmadan serbest. |
| Oy verme | Üye olmadan serbest (anonim ziyaretçiler dahil). |
| Anket oluşturma | **Sadece üyeler.** Üye olmayan "Anket oluştur"a tıklarsa giriş/kayıt sayfasına yönlendirilir, sonra geri döner. |
| Seçenek sayısı | En az **2**, en fazla **5**. |
| Kayıt bilgileri | E-posta + parola + **kullanıcı adı**. |
| Görünürlük | Anketlerde **kullanıcı adı** görünür. **E-posta hiçbir yerde görünmez** (şablonlar, JSON yanıtları, profil sayfası dahil). |
| Oy değiştirme | Prototipte **oy kesindir**, değiştirilemez / geri alınamaz. |
| Sonuçların görünmesi | Oy vermeden önce sonuçlar **gizli** (ön yargı olmasın). Oy verildikten sonra yüzdeler görünür. Anket sahibi sonuçları her zaman görür. |
| Kendi anketine oy | Serbest. |
| Anket düzenleme | Prototipte **yok** (oyları geçersiz kılar). Sahibi anketi **silebilir**. |

---

## 2. Teknoloji yığını

| Katman | Seçim | Not |
|---|---|---|
| Dil | Python 3.14 | Vercel destekliyor (3.12 varsayılan, 3.13 ve 3.14 da var). `.python-version` dosyasıyla sabitlenir. |
| Web framework | Django 5.2 (LTS) | |
| Veritabanı | Supabase (PostgreSQL) | **Sadece Postgres olarak** kullanılır. Supabase Auth, Supabase JS client, Storage vb. **kullanılmaz**. Kimlik doğrulama Django'nun kendi auth sistemiyle yapılır. |
| Yerel geliştirme DB | SQLite | `DATABASE_URL` tanımlı değilse otomatik SQLite. |
| DB sürücüsü | psycopg 3 (`psycopg[binary]`) | |
| Deploy | Vercel | Django'yu sıfır yapılandırmayla tanır (`manage.py` + `WSGI_APPLICATION`). |
| Statik dosyalar | WhiteNoise (yerel) + Vercel CDN (prod) | Vercel, `STATIC_ROOT` varsa build sırasında `collectstatic`'i kendisi çalıştırır. |
| Frontend | Django şablonları + saf HTML / CSS / JS | Framework yok, build adımı yok, npm yok. Tek repo. |

### Bağımlılıklar (`requirements.txt`)

```
Django>=5.2,<5.3
psycopg[binary]>=3.2
dj-database-url>=2.2
python-dotenv>=1.0
whitenoise>=6.7
```

Bunun dışında paket eklemek için kullanıcıya sor.

---

## 3. Proje yapısı

```
kararsizim/
├── CLAUDE.md                  # docs/PROJECT.md'yi içe aktarır + komutlar ve mimari notları
├── docs/PROJECT.md            # bu dosya
├── README.md                  # kısa kurulum talimatı
├── manage.py                  # .env dosyasını python-dotenv ile yükler
├── requirements.txt
├── .python-version            # 3.14
├── .env.example               # örnek ortam değişkenleri (gerçek değer yok)
├── .gitignore                 # .env, .env.local, db.sqlite3, staticfiles/, __pycache__/, .venv/, .vercel/
├── config/                    # Django proje paketi
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py                # `application` değişkeni
├── accounts/                  # kullanıcı modeli, kayıt / giriş / çıkış, profil
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── polls/                     # anket, seçenek, oy
│   ├── models.py
│   ├── forms.py
│   ├── services.py            # oy verme mantığı, sonuç hesaplama
│   ├── voter.py               # anonim ziyaretçi kimliği (çerez) yardımcıları
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── partials/              # _navbar.html, _poll_card.html, _messages.html, _results.html
│   ├── accounts/              # register.html, login.html, profile.html
│   ├── polls/                 # feed.html, detail.html, create.html, confirm_delete.html
│   ├── 404.html
│   └── 500.html
└── static/
    ├── css/main.css           # tek CSS dosyası, tasarım değişkenleri en üstte
    ├── js/main.js             # oylama (fetch), kopyala-paylaş, toast
    ├── js/poll-form.js        # anket formunda seçenek ekle/sil
    └── img/                   # favicon, logo (SVG)
```

---

## 4. Veri modeli

### 4.1 `accounts.User` (özel kullanıcı modeli)

> ⚠️ Özel kullanıcı modeli **ilk `migrate`'ten önce** tanımlanmalıdır. Bu yüzden Faz 0'da oluşturulur.

`AbstractUser`'dan türetilir.

| Alan | Tip | Kural |
|---|---|---|
| `email` | EmailField | `unique=True`, zorunlu. Kaydederken küçük harfe çevrilir. **Giriş e-posta ile yapılır.** |
| `username` | CharField(20) | Zorunlu, benzersiz (**büyük/küçük harf duyarsız** benzersizlik: `Lower("username")` üzerinde `UniqueConstraint`). 3–20 karakter, sadece `a-z A-Z 0-9 _ .` Türkçe karakter yok (URL'de kullanılacak). |
| `USERNAME_FIELD` | | `"email"` |
| `REQUIRED_FIELDS` | | `["username"]` |

- Yasaklı kullanıcı adları: `admin, yonetici, kararsizim, anket, giris, kayit, cikis, api, static, u, destek` (büyük/küçük harf duyarsız).
- `first_name` / `last_name` kullanılmaz (formda yok).
- `settings.AUTH_USER_MODEL = "accounts.User"`.
- Admin paneline kaydedilir (e-posta admin'de görünebilir, bu tamam — sadece son kullanıcıya gösterilmez).

### 4.2 `polls.Poll`

| Alan | Tip | Kural |
|---|---|---|
| `author` | FK → User | `on_delete=CASCADE`, `related_name="polls"` |
| `question` | CharField(200) | Zorunlu, en az 5 karakter (boşluklar kırpıldıktan sonra). |
| `description` | CharField(300) | Opsiyonel, boş olabilir. Kısa bağlam için ("Hava yağmurlu, bütçem kısıtlı" gibi). |
| `created_at` | DateTimeField | `auto_now_add=True`, indeksli. |

- `Meta.ordering = ["-created_at"]`
- `get_absolute_url()` → `/anket/<id>/`

### 4.3 `polls.Option`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `on_delete=CASCADE`, `related_name="options"` |
| `text` | CharField(80) | Zorunlu, kırpılmış, boş olamaz. |
| `position` | PositiveSmallIntegerField | 0–4, görüntüleme sırası. |

- `Meta.ordering = ["position"]`
- `UniqueConstraint(poll, position)`
- Aynı ankette iki seçenek aynı metne sahip olamaz (büyük/küçük harf duyarsız; form seviyesinde doğrulanır).
- Bir ankette 2–5 seçenek kuralı **form seviyesinde** doğrulanır.

### 4.4 `polls.Vote`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `on_delete=CASCADE`, `related_name="votes"` (sorguları kolaylaştırmak için tekrar tutulur) |
| `option` | FK → Option | `on_delete=CASCADE`, `related_name="votes"` |
| `user` | FK → User, null | Üye oyu ise dolu. `on_delete=SET_NULL` değil **CASCADE** (hesap silinirse oyları da gider). |
| `voter_token` | CharField(64), null | Anonim ziyaretçi oyu ise dolu. |
| `created_at` | DateTimeField | `auto_now_add=True` |

Kısıtlar:

- `CheckConstraint`: `user` ve `voter_token`'dan **tam olarak biri** dolu olmalı.
- `UniqueConstraint(fields=["poll", "user"], condition=Q(user__isnull=False), name="one_vote_per_user")`
- `UniqueConstraint(fields=["poll", "voter_token"], condition=Q(voter_token__isnull=False), name="one_vote_per_visitor")`
- `option.poll_id == poll_id` olmalı → `services.cast_vote` içinde kontrol edilir.

### 4.5 Oy sayıları

Prototipte sayaç alanı (denormalize kolon) **tutulmaz**. Sayılar `annotate(Count(...))` ile hesaplanır. Bu hem basit hem her zaman doğrudur. Performans sorun olursa ileride sayaç eklenir.

---

## 5. Anonim oylama tasarımı

Üye olmayan ziyaretçiler de oy verebilir. Aynı kişinin aynı ankete tekrar oy vermesini engellemek için:

- İlk oyda tarayıcıya **imzalı bir çerez** yazılır: ad `kz_voter`, değer rastgele `uuid4().hex`.
  - `response.set_signed_cookie("kz_voter", token, salt="kararsizim.voter", max_age=365 gün, httponly=True, samesite="Lax", secure=not DEBUG)`
  - Okuma: `request.get_signed_cookie("kz_voter", default=None, salt="kararsizim.voter")`
- Bu yardımcılar `polls/voter.py` içinde toplanır: `get_voter_token(request)`, `ensure_voter_token(request, response)`.
- Üye giriş yapmışsa **her zaman `user` ile** oy kaydedilir, çerez kullanılmaz.
- Çift oy denemesinde veritabanı kısıtı `IntegrityError` fırlatır → yakalanır → "Bu ankete zaten oy verdin" mesajı.

> Bilinen sınır: Anonim kullanıcı çerezlerini silerse tekrar oy verebilir. Prototip için kabul edilir. İleride IP tabanlı hız sınırı veya "sadece üyeler oy verebilir" seçeneği eklenebilir.

---

## 6. Sayfalar ve URL'ler

| URL | View | Yetki | Açıklama |
|---|---|---|---|
| `/` | `feed` | Herkes | Tüm anketler, en yeniden eskiye, sayfa başına 20 (`?sayfa=2`). |
| `/anket/yeni/` | `poll_create` | Üye | Anket oluşturma formu. |
| `/anket/<id>/` | `poll_detail` | Herkes | Tek anket; paylaşılabilir link. |
| `/anket/<id>/oy/` | `poll_vote` | Herkes | Sadece `POST`. HTML form ve `fetch` ile çalışır. |
| `/anket/<id>/sil/` | `poll_delete` | Sadece sahibi | `GET`: onay sayfası, `POST`: siler. Sahibi değilse 404. |
| `/kayit/` | `register` | Anonim | Kayıt sonrası otomatik giriş + `next`'e yönlendirme. |
| `/giris/` | `login` | Anonim | E-posta + parola. `next` parametresini destekler. |
| `/cikis/` | `logout` | Üye | Sadece `POST`. |
| `/u/<username>/` | `profile` | Herkes | Kullanıcının anketleri (Faz 4). E-posta gösterilmez. |
| `/admin/` | Django admin | Süper kullanıcı | |

`LOGIN_URL = "giris"`, `LOGIN_REDIRECT_URL = "/"`, `LOGOUT_REDIRECT_URL = "/"`.

### 6.1 Oy endpoint'i (`POST /anket/<id>/oy/`)

Girdi: `option_id` (form alanı). CSRF zorunlu.

İstek `fetch` ile ve `Accept: application/json` başlığıyla gelirse JSON döner:

```json
{
  "ok": true,
  "poll_id": 12,
  "total_votes": 37,
  "voted_option_id": 45,
  "options": [
    {"id": 44, "text": "Sinema", "votes": 20, "percent": 54},
    {"id": 45, "text": "Restoran", "votes": 17, "percent": 46}
  ]
}
```

Hata durumları (JSON):

| Durum | HTTP | `error` |
|---|---|---|
| Geçersiz / bu ankete ait olmayan seçenek | 400 | `"Geçersiz seçenek."` |
| Zaten oy verilmiş | 409 | `"Bu ankete zaten oy verdin."` (+ güncel sonuçlar) |
| Anket yok | 404 | |

JSON istenmemişse (JS kapalı): mesaj framework'üyle bildirim eklenir ve `next` parametresine ya da anket detayına yönlendirilir. **Uygulama JS olmadan da çalışmalıdır** (progressive enhancement).

JSON yanıtlarında **asla e-posta veya kullanıcı kimliği dışında kişisel veri** bulunmaz.

---

## 7. Formlar ve doğrulama

### Kayıt formu
- Alanlar: `username`, `email`, `password1`, `password2`.
- Django'nun parola doğrulayıcıları açık (minimum 8 karakter vb.), mesajlar Türkçe (`LANGUAGE_CODE = "tr"` ile otomatik).
- E-posta zaten kayıtlıysa: "Bu e-posta ile zaten bir hesap var."
- Kullanıcı adı alınmışsa: "Bu kullanıcı adı alınmış."
- Kullanıcı adı alanının altında yardım metni: "3–20 karakter; harf, rakam, _ ve . kullanabilirsin. Anketlerinde bu isim görünecek."
- E-posta alanının altında: "E-postan kimseye gösterilmez."

### Giriş formu
- Alanlar: `email`, `password`. Hatalı girişte: "E-posta veya parola hatalı."

### Anket oluşturma formu
- `question` (zorunlu), `description` (opsiyonel), seçenekler.
- Seçenekler için Django **formset** kullanılır (`formset_factory`, `min_num=2`, `max_num=5`, `validate_min=True`, `validate_max=True`, `extra=0`). Başlangıçta 2 boş seçenek görünür.
- `poll-form.js`: "+ Seçenek ekle" butonu (5'e ulaşınca gizlenir), her seçeneğin yanında "×" sil butonu (2'nin altına inilemez). `TOTAL_FORMS` yönetim alanını günceller.
- Tamamen boş bırakılan seçenek satırları yok sayılır; kalan doluların sayısı 2–5 aralığında olmalı.
- Tekrarlanan seçenek: "Aynı seçeneği iki kez yazmışsın."
- Kaydetme `transaction.atomic()` içinde: önce Poll, sonra Option'lar (`position` sırasıyla).
- Başarılıysa anket detay sayfasına yönlendirilir + "Anketin yayında! 🎉" mesajı.

---

## 8. Sorgu ve performans notları

- Akışta N+1 sorgu olmamalı:
  - `Poll.objects.select_related("author").annotate(total_votes=Count("votes")).prefetch_related(Prefetch("options", queryset=Option.objects.annotate(vote_count=Count("votes"))))`
  - Mevcut ziyaretçinin oy verdiği anketler **tek sorguda** alınır: `Vote.objects.filter(poll_id__in=[...], user=...)` veya `voter_token=...` → `{poll_id: option_id}` sözlüğü.
- Sonuç yüzdeleri `services.build_results(poll)` içinde hesaplanır; toplam 0 ise tümü 0. Yuvarlanmış yüzdeler toplamı 100'ü geçmemeli (en büyük kalan yöntemi veya basit yuvarlama + son seçeneği düzeltme).
- Anket akışında `Paginator` ile sayfalama.

---

## 9. Ayarlar (`config/settings.py`)

Ortam değişkenleriyle yönetilir; `manage.py` başında `load_dotenv()` çağrılır (yerelde `.env` okunsun diye).

| Değişken | Yerel varsayılan | Açıklama |
|---|---|---|
| `DJANGO_SECRET_KEY` | geliştirme için sabit bir dev anahtarı | Prod'da zorunlu. `DEBUG=False` iken tanımlı değilse uygulama hata vermeli. |
| `DJANGO_DEBUG` | `True` | Prod'da `False`. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,.vercel.app` | Virgülle ayrılmış. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | boş | Örn. `https://kararsizim.vercel.app` |
| `DATABASE_URL` | tanımsız → SQLite | Supabase **Transaction pooler** bağlantı dizesi (port 6543). |

Diğer ayarlar:

```python
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

AUTH_USER_MODEL = "accounts.User"
WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS += ["django.contrib.humanize", "accounts", "polls"]  # humanize: "3 dakika önce"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# MIDDLEWARE: SecurityMiddleware'den hemen sonra "whitenoise.middleware.WhiteNoiseMiddleware"
# STORAGES["staticfiles"]: DEBUG=False iken
#   "whitenoise.storage.CompressedManifestStaticFilesStorage", aksi halde varsayılan.
#   (Testlerde manifest hatası olmasın diye.)

# Veritabanı
DATABASES = {"default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=0)}
# Postgres ise (Supabase transaction pooler için):
#   DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
#   DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"
#   Prepared statement kullanılmamalı (transaction mode desteklemez):
#   OPTIONS["prepare_threshold"] = None

# Prod güvenlik (DEBUG=False iken)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
```

Oturumlar varsayılan veritabanı backend'inde kalır (Supabase'de tutulur; Vercel'in dosya sistemi kalıcı değildir, dosya tabanlı hiçbir şey kullanılmaz).

---

## 10. Arayüz ve tasarım rehberi

### Hedef his
Gençlere hitap eden, **açık (krem/beyaz) arka planlı**, **canlı renk vurguları** olan, temiz ve eğlenceli bir arayüz. Kalabalık değil; bol boşluk, büyük yuvarlatılmış kartlar, "tıklamak istenen" tombul butonlar. **Mobil öncelikli** tasarlanır (çoğu kullanıcı telefondan girecek).

### Renk paleti (CSS değişkenleri, `main.css` en üstü)

```css
:root {
  /* Zemin ve metin */
  --bg: #FFF8F1;          /* sıcak krem arka plan */
  --surface: #FFFFFF;     /* kartlar */
  --ink: #1E1A2E;         /* ana metin */
  --muted: #6D6880;       /* ikincil metin */
  --line: #EDE6F5;        /* kenarlıklar */

  /* Vurgu renkleri */
  --violet: #7C3AED;      /* birincil (butonlar, linkler) */
  --pink:   #FF3D8B;
  --orange: #FF8A1F;
  --teal:   #10B3A3;
  --sky:    #2F9BFF;
  --sun:    #FFC928;      /* küçük vurgular, rozetler */

  /* Yumuşak tonlar (seçenek arka planları, rozetler) */
  --violet-soft: #F1E8FF;
  --pink-soft:   #FFE6F0;
  --orange-soft: #FFEEDD;
  --teal-soft:   #DDF7F3;
  --sky-soft:    #E2F0FF;

  --radius-lg: 22px;
  --radius-md: 14px;
  --shadow-card: 0 8px 24px rgba(124, 58, 237, 0.08);
  --shadow-pop: 0 4px 0 rgba(30, 26, 46, 0.9); /* tombul buton gölgesi */
}
```

- **Seçenek renkleri:** 5 seçenek = 5 renk. Sırasıyla `violet, pink, orange, teal, sky`. Her seçeneğin sonuç çubuğu kendi rengiyle, arka planı kendi `-soft` tonuyla.
- **"Ton" efekti:** `body` arka planında 2–3 büyük, çok bulanık, düşük opaklıkta renk lekesi (`radial-gradient` ile, `position: fixed`, pembe ve mor ağırlıklı). Zemin açık kalır, sadece hafif renk tonu verir.
- **Kontrast:** Beyaz metin sadece `--violet` üzerinde kullanılır. Pembe/turuncu/sarı zeminlerde koyu (`--ink`) metin. Metin kontrastı en az WCAG AA (4.5:1).

### Tipografi
- Başlıklar: **Bricolage Grotesque** (Google Fonts, 700–800) — karakterli ve genç.
- Gövde: **Plus Jakarta Sans** (400, 500, 700).
- İki font da Türkçe karakterleri (ş, ğ, ı, İ, ç, ö, ü) destekler; `&subset=latin-ext` gerekmez ama ş/ğ/İ görünümünü kontrol et.
- Temel yazı boyutu 16px, anket sorusu 20–22px, sayfa başlıkları 28–36px.

### Bileşenler
- **Navbar:** Solda logo ("Kararsızım" kelimesi + eğik duran renkli bir "?" işareti, SVG). Sağda: anonimse "Giriş yap" (metin link) + "Kayıt ol" (birincil buton); üyeyse "+ Anket oluştur" (birincil buton) + `@kullaniciadi` + "Çıkış".
- **Anket kartı:**
  - Üst satır: renkli avatar dairesi (kullanıcı adının baş harfi; renk kullanıcı adından deterministik seçilir) + `@kullaniciadi` + "· 5 dakika önce".
  - Soru (kalın), varsa açıklama (gri, küçük).
  - Seçenekler: tam genişlikte, yuvarlatılmış, tıklanabilir butonlar (kendi `-soft` renginde, solda küçük renkli nokta).
  - Oy verildikten sonra: butonlar sonuç çubuğuna dönüşür — çubuk soldan sağa **animasyonla dolar** (0 → %X, ~600ms), sağda yüzde, seçilen seçenekte ✓ işareti ve kalın kenarlık.
  - Alt satır: "37 oy" + "Linki kopyala" butonu + (sahibiyse) "Sil".
- **Birincil buton:** mor zemin, beyaz metin, `--radius-md`, koyu alt gölge (`--shadow-pop`); tıklanınca 2px aşağı "basılır".
- **Boş durum (hiç anket yoksa):** büyük bir emoji 🤔 + "Burası çok sessiz... İlk kararsızlığı sen paylaş!" + "Anket oluştur" butonu.
- **Bildirimler (toast):** Sağ altta (mobilde altta ortada) kayan küçük kart; 3 saniyede kaybolur. Django mesajları da bu stilde gösterilir.
- **Formlar:** Büyük input'lar (min 48px yükseklik), odakta mor halka (`outline: 3px solid var(--violet-soft)` + mor kenarlık). Hata mesajları inputun altında pembe.

### Mikro metinler (örnekler)
- Akış başlığı: "Herkes bir şeye karar veremiyor 👀"
- Anket oluştur sayfası başlığı: "Neye karar veremiyorsun?"
- Soru placeholder: "Bu akşam sinema mı, restoran mı?"
- Seçenek placeholder: "1. seçenek", "2. seçenek"…
- Oy sonrası toast: "Oyun kaydedildi! ✨"
- Anonim kullanıcıya akış üstünde ince bir bant: "Sen de sor! Anket açmak için ücretsiz üye ol →"

### Erişilebilirlik ve davranış
- Tüm etkileşimli öğeler klavyeyle kullanılabilir, görünür `:focus-visible` stili var.
- Seçenek butonları gerçek `<button type="submit" name="option_id" value="...">` öğeleridir (JS olmadan da çalışır).
- `prefers-reduced-motion` açıksa animasyonlar kapatılır.
- Kullanıcı içeriği JS'de DOM'a eklenirken **her zaman `textContent`** kullanılır, asla `innerHTML` ile kullanıcı verisi eklenmez.
- `fetch` isteklerinde CSRF token `<meta name="csrf-token">` etiketinden okunur ve `X-CSRFToken` başlığıyla gönderilir.

---

## 11. Fazlar

Her faz tek başına çalışır durumda bitmelidir. Önerilen sıra 0 → 5. Faz 5 (deploy) istenirse Faz 2'den sonra da yapılabilir; ayarlar baştan deploy'a uygun yazılır.

---

### Faz 0 — İskelet ve temel ayarlar

**Amaç:** Çalışan boş bir Django projesi, ortam değişkenli ayarlar, özel kullanıcı modeli ve temel şablon.

**Yapılacaklar**
1. `requirements.txt`, `.python-version` (3.14), `.gitignore`, `.env.example`, kısa `README.md` oluştur.
2. `config` adlı Django projesi ve `accounts`, `polls` uygulamalarını oluştur (bölüm 3'teki yapı).
3. `settings.py`'yi bölüm 9'a göre yaz (env değişkenleri, SQLite/Postgres geçişi, WhiteNoise, Türkçe, İstanbul saat dilimi).
4. `manage.py` başında `from dotenv import load_dotenv; load_dotenv()`.
5. `accounts.User` modelini bölüm 4.1'e göre oluştur, `AUTH_USER_MODEL`'i ayarla, admin'e kaydet. **Sonra** ilk migration'ları oluştur ve uygula.
6. `templates/base.html`: Google Fonts, `main.css`, `main.js`, CSRF meta etiketi, navbar ve mesaj alanı için yer tutucular, `{% block content %}`.
7. `static/css/main.css`: bölüm 10'daki CSS değişkenleri, sıfırlama (reset), temel tipografi, arka plan renk lekeleri, `.container`, `.btn`, `.card` temel sınıfları.
8. `/` adresinde geçici bir ana sayfa: logo + "Kararsızım yakında burada 🤔".
9. `404.html` ve `500.html` (basit, markaya uygun).

**Kabul kriterleri**
- `python manage.py runserver` ile `/` açılıyor, fontlar ve renkler yüklenmiş görünüyor.
- `python manage.py check` hatasız.
- `python manage.py createsuperuser` e-posta + kullanıcı adı soruyor; `/admin/` çalışıyor.
- `.env` git'e girmiyor.

**Testler**
- Kullanıcı e-posta ile oluşturulabiliyor, e-posta küçük harfe çevriliyor.
- Aynı kullanıcı adı farklı harf büyüklüğüyle ikinci kez kullanılamıyor (`Ali` / `ali`).

---

### Faz 1 — Hesaplar (kayıt, giriş, çıkış)

**Amaç:** Kullanıcılar e-posta, kullanıcı adı ve parolayla kayıt olup giriş yapabilsin.

**Yapılacaklar**
1. `accounts/forms.py`: `RegisterForm` (bölüm 7), `EmailLoginForm`. Kullanıcı adı regex ve yasaklı ad kontrolü.
2. View'lar: `register`, `login` (Django'nun `LoginView`'ı özelleştirilebilir), `logout` (sadece POST).
3. Kayıt sonrası otomatik giriş; `next` parametresi varsa oraya (güvenli URL kontrolüyle — `url_has_allowed_host_and_scheme`), yoksa `/`.
4. Giriş yapmış kullanıcı `/kayit/` veya `/giris/`'e giderse `/`'e yönlendir.
5. Şablonlar: `register.html`, `login.html` — ortalanmış tek kart, büyük inputlar, formlar arası link ("Hesabın yok mu? Kayıt ol").
6. Navbar'ı giriş durumuna göre tamamla (bölüm 10). Çıkış butonu küçük bir POST formu.
7. Mesajlar (toast) sistemini `base.html`'e bağla.

**Kabul kriterleri**
- Kayıt → otomatik giriş → navbar'da `@kullaniciadi` görünüyor.
- Çıkış → giriş → aynı kullanıcı.
- Hatalı formlarda Türkçe, alan altında hata mesajı.
- Hiçbir sayfada e-posta başka kullanıcılara görünmüyor.

**Testler**
- Başarılı kayıt, tekrar eden e-posta, tekrar eden kullanıcı adı (harf duyarsız), geçersiz kullanıcı adı (`ali veli`, `şule`, `ab`), yasaklı ad (`Admin`).
- E-posta ile giriş başarılı / hatalı parola başarısız.
- `next` ile yönlendirme; dış alan adına yönlendirme engelleniyor.
- `GET /cikis/` çıkış yaptırmıyor.

---

### Faz 2 — Anket oluşturma ve listeleme

**Amaç:** Üyeler anket açabilsin; herkes akışı ve anket detayını görebilsin (oylama henüz yok).

**Yapılacaklar**
1. `Poll`, `Option`, `Vote` modellerini bölüm 4'e göre tüm kısıtlarıyla oluştur (Vote bu fazda sadece model olarak eklenir). Migration. Admin kayıtları (Poll admin'inde Option inline).
2. `polls/forms.py`: `PollForm` + seçenek formseti (bölüm 7).
3. `poll_create` view'ı (`@login_required`); anonimse `/giris/?next=/anket/yeni/`.
4. `static/js/poll-form.js`: seçenek ekle/sil (2–5), `TOTAL_FORMS` güncelleme, 5'te "ekle" butonunu gizle.
5. `feed` view'ı: sayfalı liste, bölüm 8'deki sorgu optimizasyonu.
6. `poll_detail` view'ı.
7. `poll_delete`: sahibine onay sayfası + POST ile silme; başkasıysa 404.
8. `partials/_poll_card.html`: akış ve detayda aynı kart. Bu fazda seçenekler **oylanamaz görünümde** (sadece listelenir) veya butonlar pasif.
9. Boş durum tasarımı, anonimler için "Sen de sor!" bandı.
10. `humanize` ile "5 dakika önce" zaman gösterimi.

**Kabul kriterleri**
- Üye 2–5 seçenekli anket oluşturabiliyor; 1 veya 6 seçenekle form reddediyor (JS kapalıyken bile, sunucu tarafında).
- Anonim kullanıcı akışı ve detayı görebiliyor, "Anket oluştur"da girişe yönleniyor, girişten sonra forma dönüyor.
- Kartlarda kullanıcı adı var, e-posta yok.
- Akış sayfası anket sayısından bağımsız olarak sabit sayıda sorgu çalıştırıyor.

**Testler**
- Geçerli anket oluşturma (Poll + doğru sırada Option'lar).
- 1 seçenek, 6 seçenek, tekrarlanan seçenek, boş soru → hata.
- Anonim POST `/anket/yeni/` → giriş sayfasına yönlendirme, kayıt oluşmaz.
- Başkasının anketini silme → 404; sahibi silebilir.
- Akış sorgu sayısı `assertNumQueries` ile sabit (ör. 5 anket ve 25 anket için aynı).

---

### Faz 3 — Oylama ve sonuçlar

**Amaç:** Üyeler ve anonim ziyaretçiler oy verebilsin, sonuçlar yüzde çubuklarıyla görünsün.

**Yapılacaklar**
1. `polls/voter.py`: imzalı çerez yardımcıları (bölüm 5).
2. `polls/services.py`:
   - `cast_vote(poll, option_id, user=None, voter_token=None) -> Vote` — seçeneğin ankete ait olduğunu doğrular, `IntegrityError`'ı `AlreadyVoted` istisnasına çevirir.
   - `build_results(poll) -> dict` — bölüm 6.1'deki JSON yapısı.
   - `get_user_votes(polls, request) -> {poll_id: option_id}` — tek sorgu.
3. `poll_vote` view'ı (sadece POST): JSON ve normal form yanıtı (bölüm 6.1). Anonimse gerekirse yeni `kz_voter` çerezi yazılır.
4. Kart şablonu üç duruma göre render edilir:
   - **Oy verilmemiş:** tıklanabilir seçenek butonları (`<form method="post">` içinde).
   - **Oy verilmiş:** sonuç çubukları, yüzdeler, seçilen seçenekte ✓.
   - **Sahibi, oy vermemiş:** sonuçlar görünür + "Sen de oy verebilirsin" ile butonlar.
     (Basit tutmak için: sahip için sonuçlar gösterilir ve seçenekler yine tıklanabilir.)
5. `static/js/main.js`: seçenek butonuna tıklanınca `fetch` ile oy gönder (`Accept: application/json`, `X-CSRFToken`), yanıta göre kartı yerinde sonuç görünümüne çevir, çubukları animasyonla doldur, toast göster. Hata (409/400) durumunda toast ile bildir. Çift tıklamayı engellemek için istek sürerken butonları pasif yap.
6. JS kapalıyken normal form POST → yönlendirme → sonuçlar görünür.

**Kabul kriterleri**
- Anonim kullanıcı oy verebiliyor; sayfayı yenileyince sonuçları görüyor, tekrar oy veremiyor.
- Üye oy verebiliyor; farklı tarayıcıdan aynı üyeyle girince yine tekrar oy veremiyor.
- Oy verildikten sonra sayfa yenilenmeden kart sonuç görünümüne geçiyor.
- Başka bir anketin seçeneğiyle oy gönderilemiyor.
- Yüzdelerin toplamı 100'ü geçmiyor; 0 oyda hata yok.

**Testler**
- Anonim oy → çerez yazılıyor, Vote'ta `voter_token` dolu, `user` boş.
- Aynı çerezle ikinci oy → 409.
- Üye oyu → `user` dolu; ikinci oy → 409.
- Yanlış ankete ait `option_id` → 400.
- `GET /anket/<id>/oy/` → 405.
- JSON yanıtında `email` anahtarı hiçbir yerde yok.
- `build_results` yüzde hesabı (0 oy, eşit oy, 1/3–1/3–1/3 yuvarlama).

---

### Faz 4 — Arayüz cilası ve küçük özellikler

**Amaç:** Prototipi gösterilebilir, keyifli ve mobilde kusursuz hale getirmek.

**Yapılacaklar**
1. Tüm sayfaları bölüm 10'daki tasarım rehberiyle karşılaştır ve eksikleri tamamla (renkler, fontlar, boşluklar, gölgeler, buton basılma efekti).
2. Mobil kontrol: 360px, 390px, 768px ve masaüstü genişliklerinde yatay kaydırma olmadan düzgün görünüm. Dokunma hedefleri en az 44px.
3. Profil sayfası `/u/<username>/`: avatar dairesi, `@kullaniciadi`, "Katılma: Eylül 2026", açtığı anket sayısı ve anketleri (aynı kart bileşeni). E-posta yok. Kartlardaki kullanıcı adları profile link verir.
4. "Linki kopyala" butonu: `navigator.clipboard` ile anket linkini kopyala, toast "Link kopyalandı!". Destek yoksa `navigator.share` veya link seçimi.
5. Oy animasyonları ve küçük bir "pop" efekti; `prefers-reduced-motion` desteği.
6. Favicon ve SVG logo.
7. `<title>` ve temel meta etiketleri: her anket detayında `og:title` = soru, `og:description` = "Sen olsan hangisini seçerdin? Kararsızım'da oy ver." (link paylaşımları güzel görünsün).
8. 404/500 sayfalarının son hali.
9. Klavye ile gezinme ve odak stillerinin kontrolü.

**Kabul kriterleri**
- Telefon genişliğinde tüm akışlar (kayıt, anket açma, oy verme) rahatça yapılabiliyor.
- Görsel olarak tutarlı: tüm butonlar, kartlar ve formlar aynı sistemden.
- Lighthouse erişilebilirlik puanı 90+ (yerelde kontrol).

**Testler**
- Profil sayfası 200 döner, e-posta içermez; olmayan kullanıcı adı → 404.
- Kullanıcı adı büyük/küçük harf farkıyla da profil bulunur (`/u/Ali/` = `/u/ali/`).

---

### Faz 5 — Supabase ve Vercel ile yayına alma

**Amaç:** Uygulama Supabase Postgres ile Vercel'de canlıda çalışsın.

**Kullanıcının elle yapacakları (Claude Code adım adım anlatır)**
1. **Supabase:** Yeni proje oluştur → "Connect" menüsünden iki bağlantı dizesi al:
   - **Transaction pooler** (port **6543**) → uygulamanın çalışma zamanı için (`DATABASE_URL`). Serverless için doğru olan budur ve IPv4 uyumludur.
   - **Session pooler** (port **5432**) → yerelden `migrate` çalıştırmak için.
2. Supabase'in otomatik Data API'si (PostgREST) bu projede kullanılmıyor. Django tabloları `public` şemasında oluşacağı için ya Data API'yi kapat ya da tablolar için RLS'yi etkinleştir; Supabase panelindeki **Security Advisor** uyarılarını kontrol et.
3. **Migration:** Yerelde geçici olarak session pooler dizesiyle:
   `DATABASE_URL="postgresql://...:5432/postgres" python manage.py migrate`
   ardından `createsuperuser`.
4. **Vercel:** Repoyu GitHub'a gönder → Vercel'de "Import Project" → Django otomatik algılanır. Ortam değişkenlerini ekle:
   - `DJANGO_SECRET_KEY` (yeni, uzun, rastgele)
   - `DJANGO_DEBUG=False`
   - `DATABASE_URL` (transaction pooler, 6543)
   - `DJANGO_ALLOWED_HOSTS=.vercel.app` (+ varsa özel alan adı)
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<proje-adi>.vercel.app`
5. Deploy et.

**Claude Code'un yapacakları**
1. Ayarların bölüm 9'daki prod kurallarını tam karşıladığını doğrula (`python manage.py check --deploy` uyarılarını incele, prototip için makul olanları düzelt).
2. `DATABASE_URL` Postgres ise: `conn_max_age=0`, `DISABLE_SERVER_SIDE_CURSORS=True`, `sslmode=require`, `prepare_threshold=None`.
3. `STATIC_ROOT` tanımlı olduğundan Vercel `collectstatic`'i kendisi çalıştırır; ayrıca build script'i gerekmez. `vercel.json` yalnızca gerekirse eklenir.
4. `README.md`'ye "Yayına alma" bölümü ekle (yukarıdaki adımların kısa hali).
5. Canlı ortamda kontrol listesi: kayıt, giriş, anket açma, anonim oy (gizli pencereden), üye oyu, silme, statik dosyalar, 404 sayfası.

**Kabul kriterleri**
- `https://<proje>.vercel.app` açılıyor, CSS/JS yükleniyor.
- Kontrol listesindeki tüm akışlar canlıda çalışıyor.
- `DEBUG=False`; hata sayfalarında iz (traceback) görünmüyor.
- Gizli değerler repoda yok.

**Bilinen notlar**
- Supabase ücretsiz projeleri bir süre hareketsiz kalınca duraklatılabilir; panelden yeniden başlatılır.
- Vercel fonksiyonlarının dosya sistemi kalıcı değildir; dosyaya yazan hiçbir özellik eklenmez.

---

## 12. Kapsam dışı (ileride eklenebilir)

Prototipte **yapılmayacak**, sonraki adımlar için fikirler:

- Parola sıfırlama ve e-posta doğrulama (e-posta gönderim servisi gerektirir)
- "Popüler" / "Yeni" sekmeleri, arama, kategoriler / etiketler
- Anket süresi ve otomatik kapanma, "karar verdim" ile anketi kapatma
- Yorumlar veya emoji tepkileri
- Oy değiştirme / geri alma
- Hız sınırlama (rate limit) ve spam/kötüye kullanım raporlama, moderasyon
- Anonim oylamayı kapatabilme seçeneği (anket sahibine)
- Görsel yükleme (seçeneklere fotoğraf)
- Karanlık mod
- Bildirimler

---

## 13. İlerleme Durumu

Claude Code her faz bitiminde burayı günceller.

- [x] Faz 0 — İskelet ve temel ayarlar (2026-09-26)
- [x] Faz 1 — Hesaplar (2026-09-29)
- [x] Faz 2 — Anket oluşturma ve listeleme (2026-10-03)
- [x] Faz 3 — Oylama ve sonuçlar (2026-10-03)
- [ ] Faz 4 — Arayüz cilası
- [ ] Faz 5 — Supabase + Vercel yayını

### Notlar / alınan kararlar
<!-- Faz sırasında verilen ek kararlar buraya kısa maddelerle yazılır. -->
- 2026-09-26: Python sürümü 3.12 yerine **3.14** (yerelde yalnızca 3.14 kurulu; Vercel 3.14'ü destekliyor).
- 2026-09-26: Bu dosya `docs/` içinde kalır; kökteki `CLAUDE.md` onu içe aktarır.
- 2026-09-29: Spec dosyası `docs/CLAUDE.md` → `docs/PROJECT.md` olarak yeniden adlandırıldı; kökteki `CLAUDE.md` artık `@docs/PROJECT.md` ile içe aktarıyor.
- 2026-09-26: Git şimdilik kullanılmıyor; kullanıcı daha sonra kendisi başlatacak. `.gitignore` hazır (`.idea/` de eklendi).
- 2026-09-29: Kullanıcının isteğiyle git deposu başlatıldı (`main` dalı); commit yalnızca kullanıcı isteyince atılır.
- 2026-09-26: Kullanıcı adı format ve yasaklı ad doğrulayıcıları modelde tanımlı (`accounts/models.py`); Faz 1 formları bunları otomatik kullanır.
- 2026-09-26: Faz 0'daki geçici ana sayfa `polls.views.home`; Faz 2'de akış ile değiştirilecek. `config/asgi.py` kaldırıldı (Vercel WSGI kullanıyor).
- 2026-09-29: Form hata metinleri için `--pink-ink: #C8105F` eklendi; `--pink` beyaz zeminde WCAG AA'yı (4.5:1) geçmiyor. Input kenarlığı hatada yine `--pink`.
- 2026-09-29: Giriş/kayıt/çıkış fonksiyon view'larıyla yazıldı (`accounts/views.py`); `next` kontrolü ortak `get_safe_next_url()` ile. URL adları: `accounts:register`, `accounts:login`, `accounts:logout`. `LOGIN_URL = "/giris/"`.
- 2026-09-29: Toast'lar JS olmadan da CSS animasyonuyla ~3 sn sonra kaybolur; `main.js` DOM'dan kaldırır ve Faz 3 için `kz.toast(text, kind)` yardımcısını sağlar.
- 2026-09-29: Navbar'daki "+ Anket oluştur" `/anket/yeni/` adresine gidiyor; bu sayfa Faz 2'ye kadar 404 döner.
- 2026-09-30: Supabase, Faz 5'ten önce bağlandı (Supabase MCP ile). Proje: **`kararsizim-eu`** (id `nlxgpagqfsuepdoyhrba`, `eu-central-1` Frankfurt, ücretsiz plan). İlk açılan Mumbai (`ap-south-1`) projesi gecikme nedeniyle silindi.
- 2026-09-30: Yerel `.env` → `DATABASE_URL` = **session pooler** (`aws-1-eu-central-1.pooler.supabase.com:5432`); yerelde hem `runserver` hem `migrate` Supabase'e gider. Vercel'de Faz 5'te **transaction pooler** (6543) kullanılacak.
- 2026-09-30: `manage.py test` her zaman yerel SQLite kullanır (`config/settings.py`); testler Supabase'de test veritabanı açmaz.
- 2026-09-30: Supabase güvenliği: `public` şemasındaki tüm tablolarda RLS açık, politika yok (Data API'nin `anon`/`authenticated` rolleri hiçbir satır göremez; Django tablo sahibi `postgres` rolüyle bağlandığı için etkilenmez). `enable_rls_on_new_public_tables` event trigger'ı, sonraki Django migration'larıyla oluşan tablolarda RLS'yi otomatik açar. Security Advisor'da yalnızca beklenen INFO uyarısı ("RLS enabled, no policy") kalır.
- 2026-10-03: Faz 2'de `polls` tabloları Supabase'e uygulandı; event trigger RLS'yi otomatik açtı.
- 2026-10-03: `annotate(Count(...))` içeren sorgularda Django `Meta.ordering`'i uygulamaz (GROUP BY). Akış ve seçenek sorguları bu yüzden açıkça `order_by("-created_at", "-pk")` / `order_by("position")` kullanır (`polls.views.polls_with_counts`).
- 2026-10-03: Option'a ek DB kısıtı: `position < 5` (`option_position_range`). Avatar rengi `User.avatar_color` (kullanıcı adının `crc32`'si; süreçler arasında sabit).
- 2026-10-03: JS kapalıyken anket formu yalnızca sunucunun çizdiği 2 seçenek satırıyla çalışır (daha fazla satır `poll-form.js` ile eklenir); 2–5 kuralı yine sunucuda doğrulanır.
- 2026-10-03: Anket silme `@login_required`: anonim kullanıcı girişe yönlenir, başkasının anketi 404.
- 2026-10-03: `voter.py` API'si bölüm 5'ten biraz farklı: token oy kaydedilmeden önce gerektiği için `ensure_voter_token(request) -> (token, is_new)` + `set_voter_cookie(response, token)`. Yeni çerez yalnızca oy **başarıyla** kaydedilince yazılır (400/409'da yazılmaz).
- 2026-10-03: Yüzdeler `services.percentages()` ile "en büyük kalan" yöntemiyle hesaplanır; toplam her zaman tam 100 (0 oyda hepsi 0). Arayüzde Türkçe yazımla `%54`.
- 2026-10-03: Geçersiz/yabancı `option_id` → `InvalidOption` (400); çift oy → `AlreadyVoted` (409, güncel sonuçlar + `voted_option_id` ile). JS kapalıyken yönlendirme `next` (güvenli) veya detay sayfasına, `#anket-<id>` çapasıyla.
- 2026-10-03: Sonuç çubuğu seçeneğin renginde ama %35 opaklıkta; `--ink` metin üzerinde okunur kalsın diye (tam renkli çubukta kontrast AA'nın altında kalıyor).
- 2026-10-03: Geliştirmede tarayıcı `main.js`'in eski sürümünü önbellekten kullanabilir (runserver önbellek kırmıyor); JS değişikliğinden sonra sert yenileme gerekir. Prod'da WhiteNoise manifest dosya adları önbelleği kendiliğinden kırar.
