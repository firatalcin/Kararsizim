from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Option, Poll, Vote
from .services import build_results, percentages
from .text import clean_text, fold_key, has_visible_text
from .voter import COOKIE_NAME, get_voter_token

User = get_user_model()

CREATE_URL = reverse("polls:create")


def make_user(username="ali"):
    return User.objects.create_user(email=f"{username}@example.com", username=username, password="x")


def make_poll(author, question="Sinema mı, restoran mı?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question)
    for position, text in enumerate(options):
        Option.objects.create(poll=poll, text=text, position=position)
    return poll


def poll_data(question="Bu akşam ne yapsam?", description="", options=("Sinema", "Restoran")):
    """POST data for the create form, including the formset management form."""
    data = {
        "question": question,
        "description": description,
        "options-TOTAL_FORMS": str(len(options)),
        "options-INITIAL_FORMS": "0",
        "options-MIN_NUM_FORMS": "2",
        "options-MAX_NUM_FORMS": "5",
    }
    for index, text in enumerate(options):
        data[f"options-{index}-text"] = text
    return data


class PollCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_form_renders_two_empty_options(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, "Neye karar veremiyorsun?")
        self.assertContains(response, 'name="options-TOTAL_FORMS" value="2"')
        self.assertContains(response, 'placeholder="1. seçenek"')
        self.assertContains(response, 'placeholder="2. seçenek"')

    def test_valid_poll_is_created_with_options_in_order(self):
        data = poll_data(question="  Hafta sonu nereye?  ", options=("Deniz", "", "Dağ", "Şehir"))
        response = self.client.post(CREATE_URL, data)
        poll = Poll.objects.get()
        self.assertRedirects(response, poll.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(poll.author, self.user)
        self.assertEqual(poll.question, "Hafta sonu nereye?")
        self.assertEqual(
            list(poll.options.values_list("position", "text")),
            [(0, "Deniz"), (1, "Dağ"), (2, "Şehir")],
        )
        self.assertContains(self.client.get(poll.get_absolute_url()), "Anketin yayında!")

    def test_five_options_allowed(self):
        self.client.post(CREATE_URL, poll_data(options=("a", "b", "c", "d", "e")))
        self.assertEqual(Option.objects.count(), 5)

    def assertRejected(self, data, message):
        response = self.client.post(CREATE_URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(Option.objects.exists())

    def test_one_option_rejected(self):
        self.assertRejected(poll_data(options=("Sinema",)), "En az 2 seçenek yazmalısın.")

    def test_one_filled_option_among_blank_rows_rejected(self):
        self.assertRejected(poll_data(options=("Sinema", "   ")), "En az 2 seçenek yazmalısın.")

    def test_six_options_rejected(self):
        self.assertRejected(poll_data(options=("a", "b", "c", "d", "e", "f")), "En fazla 5 seçenek ekleyebilirsin.")

    def test_duplicate_option_rejected_case_insensitive(self):
        self.assertRejected(poll_data(options=("Sinema", "sinema ")), "Aynı seçeneği iki kez yazmışsın.")

    def test_empty_question_rejected(self):
        self.assertRejected(poll_data(question="   "), "Bir soru yazmalısın.")

    def test_short_question_rejected(self):
        self.assertRejected(poll_data(question="Ne?"), "Soru en az 5 karakter olmalı.")

    def test_too_long_option_rejected(self):
        response = self.client.post(CREATE_URL, poll_data(options=("a" * 81, "b")))
        self.assertTrue(response.context["formset"].forms[0].has_error("text"))
        self.assertFalse(Poll.objects.exists())


class PollCreateAnonymousTests(TestCase):
    def test_get_redirects_to_login_with_next(self):
        response = self.client.get(CREATE_URL)
        self.assertRedirects(response, "/giris/?next=/anket/yeni/")

    def test_post_redirects_and_creates_nothing(self):
        response = self.client.post(CREATE_URL, poll_data())
        self.assertRedirects(response, "/giris/?next=/anket/yeni/")
        self.assertFalse(Poll.objects.exists())

    def test_login_returns_to_form(self):
        User.objects.create_user(email="ali@example.com", username="ali", password="Kararsiz-Parola-2026")
        response = self.client.post(
            "/giris/", {"email": "ali@example.com", "password": "Kararsiz-Parola-2026", "next": "/anket/yeni/"}
        )
        self.assertRedirects(response, CREATE_URL)


class PollDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.poll = make_poll(self.owner)
        self.url = reverse("polls:delete", args=[self.poll.pk])

    def test_other_user_gets_404(self):
        self.client.force_login(make_user("baskasi"))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_anonymous_is_sent_to_login(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, f"/giris/?next={self.url}")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_sees_confirmation_then_deletes(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url), "Anketi silelim mi?")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

        response = self.client.post(self.url)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(Option.objects.exists())

    def test_delete_link_only_for_owner(self):
        detail = self.poll.get_absolute_url()
        self.assertNotContains(self.client.get(detail), self.url)
        self.client.force_login(make_user("baskasi"))
        self.assertNotContains(self.client.get(detail), self.url)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(detail), self.url)


class PollDetailTests(TestCase):
    def test_detail_shows_poll_with_username_not_email(self):
        poll = make_poll(make_user("ali"), options=("Sinema", "Restoran", "Evde film"))
        # Votes on a later option must not reorder options (annotate + GROUP BY drops Meta.ordering).
        Vote.objects.create(poll=poll, option=poll.options.last(), voter_token="t")
        response = self.client.get(poll.get_absolute_url())
        self.assertEqual([o.text for o in response.context["poll"].options.all()], ["Sinema", "Restoran", "Evde film"])
        self.assertContains(response, "Sinema mı, restoran mı?")
        self.assertContains(response, "@ali")
        self.assertContains(response, "Evde film")
        self.assertContains(response, "1 oy")
        self.assertNotContains(response, "ali@example.com")

    def test_missing_poll_is_404(self):
        self.assertEqual(self.client.get(reverse("polls:detail", args=[999])).status_code, 404)


class FeedTests(TestCase):
    def test_empty_state(self):
        response = self.client.get("/")
        self.assertContains(response, "Burası çok sessiz")
        self.assertContains(response, "Sen de sor!")

    def test_member_does_not_see_join_band(self):
        self.client.force_login(make_user())
        self.assertNotContains(self.client.get("/"), "Sen de sor!")

    def test_lists_polls_newest_first_without_emails(self):
        author = make_user("ali")
        make_poll(author, question="Eski anket burada")
        make_poll(author, question="Yeni anket burada")
        content = self.client.get("/").content.decode()
        self.assertLess(content.index("Yeni anket burada"), content.index("Eski anket burada"))
        self.assertIn("@ali", content)
        self.assertNotIn("ali@example.com", content)

    def test_vote_counts_are_shown(self):
        poll = make_poll(make_user())
        option = poll.options.first()
        for token in ("a", "b", "c"):
            Vote.objects.create(poll=poll, option=option, voter_token=token)
        self.assertContains(self.client.get("/"), "3 oy")

    def test_pagination(self):
        author = make_user()
        for i in range(21):
            make_poll(author, question=f"Anket numarası {i:02d}")
        first = self.client.get("/")
        self.assertEqual(len(first.context["polls"]), 20)
        self.assertContains(first, "?sayfa=2")
        second = self.client.get("/?sayfa=2")
        self.assertEqual(len(second.context["polls"]), 1)
        self.assertContains(second, "Anket numarası 00")
        # Out-of-range or junk page numbers fall back instead of erroring.
        self.assertEqual(self.client.get("/?sayfa=99").status_code, 200)
        self.assertEqual(self.client.get("/?sayfa=abc").status_code, 200)

    def feed_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get("/").status_code, 200)
        return len(queries)

    def test_query_count_does_not_grow_with_polls(self):
        authors = [make_user(f"uye{i}") for i in range(5)]

        def add_polls(count):
            for i in range(count):
                poll = make_poll(authors[i % 5], options=("Bir", "İki", "Üç"))
                Vote.objects.create(poll=poll, option=poll.options.first(), voter_token=f"t{poll.pk}")

        add_polls(5)
        self.client.get("/")  # the first visit receives the voter cookie; measure like a returning visitor
        with_five = self.feed_query_count()
        add_polls(20)
        with self.assertNumQueries(with_five):
            self.client.get("/")


class ModelConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user)
        self.option = self.poll.options.first()

    def test_vote_needs_exactly_one_of_user_or_token(self):
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=self.option)

    def test_vote_cannot_have_both_user_and_token(self):
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=self.option, user=self.user, voter_token="t")

    def test_one_vote_per_user(self):
        Vote.objects.create(poll=self.poll, option=self.option, user=self.user)
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=self.option, user=self.user)

    def test_one_vote_per_visitor(self):
        Vote.objects.create(poll=self.poll, option=self.option, voter_token="t")
        with self.assertRaises(IntegrityError):
            Vote.objects.create(poll=self.poll, option=self.option, voter_token="t")

    def test_option_position_unique_per_poll(self):
        with self.assertRaises(IntegrityError):
            Option.objects.create(poll=self.poll, text="Başka", position=0)

    def test_option_colors_follow_position(self):
        self.assertEqual([o.color for o in self.poll.options.all()], ["violet", "pink"])


class ProfileTests(TestCase):
    def setUp(self):
        self.ali = make_user("Ali")
        make_poll(self.ali, question="Ali'nin ilk anketi")
        make_poll(make_user("veli"), question="Veli'nin anketi")

    def test_profile_lists_only_users_polls_without_email(self):
        response = self.client.get("/u/Ali/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@Ali")
        self.assertContains(response, "Ali&#x27;nin ilk anketi")
        self.assertNotContains(response, "Veli&#x27;nin anketi")
        self.assertContains(response, "1 anket")
        self.assertContains(response, "Katılma: ")
        self.assertNotContains(response, "@example.com")

    def test_username_lookup_is_case_insensitive(self):
        self.assertEqual(self.client.get("/u/ali/").context["profile_user"], self.ali)
        self.assertEqual(self.client.get("/u/ALI/").context["profile_user"], self.ali)

    def test_unknown_user_is_404(self):
        self.assertEqual(self.client.get("/u/yokboylebiri/").status_code, 404)

    def test_join_month_is_turkish(self):
        self.ali.date_joined = self.ali.date_joined.replace(year=2026, month=9, day=15)
        self.ali.save()
        self.assertContains(self.client.get("/u/ali/"), "Katılma: Eylül 2026")

    def test_empty_profile_message(self):
        lonely = make_user("yalniz")
        self.assertContains(self.client.get("/u/yalniz/"), "henüz anket açmamış")
        self.client.force_login(lonely)
        self.assertContains(self.client.get("/u/yalniz/"), "Henüz anket açmadın")

    def test_navbar_links_to_own_profile(self):
        self.client.force_login(self.ali)
        self.assertContains(self.client.get("/"), 'class="navbar__user" href="/u/Ali/"')


class PageMetaTests(TestCase):
    def test_poll_detail_has_share_meta(self):
        poll = make_poll(make_user(), question="Deniz mi, dağ mı?")
        response = self.client.get(poll.get_absolute_url())
        self.assertContains(response, '<meta property="og:title" content="Deniz mi, dağ mı?">', html=False)
        self.assertContains(
            response,
            '<meta property="og:description" content="Sen olsan hangisini seçerdin? Kararsızım\'da oy ver.">',
        )
        self.assertContains(response, f'<meta property="og:url" content="http://testserver/anket/{poll.pk}/">')
        self.assertContains(response, "<title>Deniz mi, dağ mı? · Kararsızım</title>")
        # The question is the page's single h1 on the detail page.
        self.assertContains(response, '<h1 class="poll-card__question">', count=1)

    def test_skip_link_present(self):
        self.assertContains(self.client.get("/"), '<a class="skip-link" href="#main">İçeriğe geç</a>')

    def test_error_pages_render_without_context(self):
        from django.views.defaults import page_not_found, server_error

        request = RequestFactory().get("/bozuk/")
        self.assertContains(server_error(request), "Bir şeyler ters gitti", status_code=500)
        self.assertContains(page_not_found(request, Exception()), "kararsız kalıp gitmiş", status_code=404)


class PercentagesTests(TestCase):
    def test_no_votes_is_all_zero(self):
        self.assertEqual(percentages([0, 0, 0]), [0, 0, 0])

    def test_equal_votes(self):
        self.assertEqual(percentages([5, 5]), [50, 50])

    def test_thirds_sum_to_exactly_100(self):
        result = percentages([1, 1, 1])
        self.assertEqual(sum(result), 100)
        self.assertEqual(sorted(result), [33, 33, 34])

    def test_never_exceeds_100(self):
        for counts in ([1, 1, 1, 1, 1, 1], [2, 1], [1, 2, 3, 4, 5], [7, 0, 0], [1, 1, 1, 1, 3]):
            with self.subTest(counts=counts):
                self.assertEqual(sum(percentages(counts)), 100)

    def test_build_results_shape(self):
        poll = make_poll(make_user(), options=("A", "B"))
        a, b = poll.options.all()
        Vote.objects.create(poll=poll, option=a, voter_token="1")
        Vote.objects.create(poll=poll, option=a, voter_token="2")
        Vote.objects.create(poll=poll, option=b, voter_token="3")
        self.assertEqual(
            build_results(poll),
            {
                "poll_id": poll.pk,
                "total_votes": 3,
                "options": [
                    {"id": a.pk, "text": "A", "votes": 2, "percent": 67},
                    {"id": b.pk, "text": "B", "votes": 1, "percent": 33},
                ],
            },
        )


class VoteTests(TestCase):
    def setUp(self):
        self.author = make_user("sahip")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran"))
        self.sinema, self.restoran = self.poll.options.all()
        self.url = reverse("polls:vote", args=[self.poll.pk])

    def vote(self, option_id, client=None, json=True):
        headers = {"Accept": "application/json"} if json else {}
        return (client or self.client).post(self.url, {"option_id": option_id}, headers=headers)

    def test_anonymous_vote_sets_cookie_and_token(self):
        response = self.vote(self.sinema.pk)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

        vote = Vote.objects.get()
        self.assertIsNone(vote.user)
        # Read the cookie back the way the app does.
        request = RequestFactory().get("/")
        request.COOKIES[COOKIE_NAME] = self.client.cookies[COOKIE_NAME].value
        self.assertEqual(get_voter_token(request), vote.voter_token)

        data = response.json()
        self.assertEqual(data["ok"], True)
        self.assertEqual(data["poll_id"], self.poll.pk)
        self.assertEqual(data["total_votes"], 1)
        self.assertEqual(data["voted_option_id"], self.sinema.pk)
        self.assertEqual([o["percent"] for o in data["options"]], [100, 0])

    def test_same_cookie_cannot_vote_twice(self):
        self.vote(self.sinema.pk)
        response = self.vote(self.restoran.pk)
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "Bu ankete zaten oy verdin.")
        self.assertEqual(data["voted_option_id"], self.sinema.pk)
        self.assertEqual(data["total_votes"], 1)
        self.assertEqual(Vote.objects.count(), 1)

    def test_tampered_cookie_is_treated_as_new_visitor(self):
        self.client.cookies[COOKIE_NAME] = "sahte-deger"
        response = self.vote(self.sinema.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(Vote.objects.get().voter_token, "sahte-deger")

    def test_member_vote_uses_user_not_cookie(self):
        user = make_user("uye")
        self.client.force_login(user)
        response = self.vote(self.restoran.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(COOKIE_NAME, response.cookies)
        vote = Vote.objects.get()
        self.assertEqual(vote.user, user)
        self.assertIsNone(vote.voter_token)

        self.assertEqual(self.vote(self.sinema.pk).status_code, 409)
        # Same member from another browser.
        other_browser = self.client_class()
        other_browser.force_login(user)
        self.assertEqual(self.vote(self.sinema.pk, client=other_browser).status_code, 409)
        self.assertEqual(Vote.objects.count(), 1)

    def test_owner_can_vote_on_own_poll(self):
        self.client.force_login(self.author)
        self.assertEqual(self.vote(self.sinema.pk).status_code, 200)

    def test_option_from_another_poll_is_rejected(self):
        other = make_poll(self.author, question="Başka bir anket", options=("X", "Y"))
        response = self.vote(other.options.first().pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"ok": False, "error": "Geçersiz seçenek."})
        self.assertNotIn(COOKIE_NAME, response.cookies)
        self.assertFalse(Vote.objects.exists())

    def test_garbage_option_is_rejected(self):
        for option_id in ["", "abc", "1.5", "-1"]:
            with self.subTest(option_id=option_id):
                self.assertEqual(self.vote(option_id).status_code, 400)
        self.assertEqual(self.client.post(self.url, headers={"Accept": "application/json"}).status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_missing_poll_is_404(self):
        response = self.client.post(reverse("polls:vote", args=[999]), {"option_id": self.sinema.pk})
        self.assertEqual(response.status_code, 404)

    def test_json_never_contains_email(self):
        self.client.force_login(make_user("uye"))
        for response in (self.vote(self.sinema.pk), self.vote(self.sinema.pk)):
            self.assertNotIn(b"email", response.content)
            self.assertNotIn(b"@example.com", response.content)

    def test_without_js_redirects_with_message(self):
        response = self.vote(self.sinema.pk, json=False)
        self.assertRedirects(response, f"/anket/{self.poll.pk}/#anket-{self.poll.pk}", fetch_redirect_response=False)
        page = self.client.get(self.poll.get_absolute_url())
        self.assertContains(page, "Oyun kaydedildi!")
        self.assertContains(page, "option--chosen")

    def test_without_js_redirects_to_safe_next_only(self):
        response = self.client.post(self.url, {"option_id": self.sinema.pk, "next": "/?sayfa=2"})
        self.assertRedirects(response, f"/?sayfa=2#anket-{self.poll.pk}", fetch_redirect_response=False)
        response = self.client.post(self.url, {"option_id": self.sinema.pk, "next": "https://evil.example.com/"})
        self.assertRedirects(response, f"/anket/{self.poll.pk}/#anket-{self.poll.pk}", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "Bu ankete zaten oy verdin.")


class CardStateTests(TestCase):
    def setUp(self):
        self.author = make_user("sahip")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran"))
        self.sinema = self.poll.options.first()
        Vote.objects.create(poll=self.poll, option=self.sinema, voter_token="baskasi")

    def test_not_voted_sees_buttons_without_results(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, 'name="option_id"')
        self.assertNotContains(response, "option__percent")

    def test_voted_sees_results_and_check(self):
        self.client.post(reverse("polls:vote", args=[self.poll.pk]), {"option_id": self.sinema.pk})
        for url in (self.poll.get_absolute_url(), "/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, 'name="option_id"')
                self.assertContains(response, "option--chosen")
                self.assertContains(response, "%100")
                self.assertContains(response, "2 oy")

    def test_owner_sees_results_and_can_still_vote(self):
        self.client.force_login(self.author)
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, 'name="option_id"')
        self.assertContains(response, "%100")
        self.assertContains(response, "Sen de oy verebilirsin")

    def test_card_has_copy_link_and_profile_link(self):
        response = self.client.get("/")
        self.assertContains(response, f'href="/anket/{self.poll.pk}/" class="poll-card__share" data-copy-link')
        self.assertContains(response, 'href="/u/sahip/"')

    def test_feed_query_count_constant_for_voter_with_cookie(self):
        self.client.post(reverse("polls:vote", args=[self.poll.pk]), {"option_id": self.sinema.pk})
        with CaptureQueriesContext(connection) as queries:
            self.client.get("/")
        for i in range(10):
            make_poll(self.author, question=f"Ek anket {i}", options=("Bir", "İki"))
        with self.assertNumQueries(len(queries)):
            self.client.get("/")


def limits(**overrides):
    return {**settings.THROTTLE_LIMITS, **overrides}


class CleanTextTests(TestCase):
    def test_zero_width_and_bidi_control_characters_are_removed(self):
        self.assertEqual(clean_text("Ev​et‮!"), "Evet!")

    def test_emoji_sequences_keep_their_joiners(self):
        family = "👨‍👩‍👧 aile"
        self.assertEqual(clean_text(family), family)

    def test_text_is_composed_and_whitespace_collapsed(self):
        self.assertEqual(clean_text("  café   güzel \n mi "), "café güzel mi")

    def test_multiline_keeps_line_breaks(self):
        self.assertEqual(clean_text(" bir\niki \n", multiline=True), "bir\niki")

    def test_has_visible_text(self):
        for value in ("a", "😀", "?", "‍😀"):
            self.assertTrue(has_visible_text(value), value)
        for value in ("", "   ", "​", "‍", " ", "\n"):
            self.assertFalse(has_visible_text(value), repr(value))

    def test_fold_key_treats_turkish_i_variants_alike(self):
        self.assertEqual(fold_key("Işık"), fold_key("IŞIK"))
        self.assertEqual(fold_key("İstanbul"), fold_key("istanbul"))
        self.assertEqual(fold_key("ISPARTA"), fold_key("Isparta"))
        self.assertNotEqual(fold_key("Sinema"), fold_key("Restoran"))


class PollTextCleaningTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user())

    def assertRejected(self, data, message):
        response = self.client.post(CREATE_URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertFalse(Poll.objects.exists())

    def test_question_made_only_of_invisible_characters_is_rejected(self):
        self.assertRejected(poll_data(question="​" * 6), "Soru boş görünüyor.")

    def test_question_too_short_once_invisible_characters_are_gone_is_rejected(self):
        self.assertRejected(poll_data(question="Ne?​​"), "Soru en az 5 karakter olmalı.")

    def test_option_made_only_of_invisible_characters_is_rejected(self):
        self.assertRejected(poll_data(options=("Sinema", "​")), "Seçenek boş görünüyor.")

    def test_options_that_differ_only_by_invisible_characters_are_duplicates(self):
        self.assertRejected(poll_data(options=("Evet", "Ev​et")), "Aynı seçeneği iki kez yazmışsın.")

    def test_turkish_case_variants_are_duplicates(self):
        self.assertRejected(poll_data(options=("Işık", "IŞIK")), "Aynı seçeneği iki kez yazmışsın.")
        self.assertRejected(poll_data(options=("İstanbul", "istanbul")), "Aynı seçeneği iki kez yazmışsın.")

    def test_stored_text_is_cleaned(self):
        data = poll_data(question="  Hafta​ sonu  nereye?  ", description="​", options=("Deniz‮", "Dağ"))
        self.client.post(CREATE_URL, data)
        poll = Poll.objects.get()
        self.assertEqual(poll.question, "Hafta sonu nereye?")
        self.assertEqual(poll.description, "")
        self.assertEqual(list(poll.options.values_list("text", flat=True)), ["Deniz", "Dağ"])


class ResultsHiddenTests(TestCase):
    """Percentages must not be in the HTML of someone who may not see them yet."""

    def setUp(self):
        self.author = make_user("sahip")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran"))
        self.sinema = self.poll.options.first()
        Vote.objects.create(poll=self.poll, option=self.sinema, voter_token="baskasi")
        self.url = self.poll.get_absolute_url()

    def test_visitor_who_has_not_voted_gets_no_percentages(self):
        for url in (self.url, "/", "/u/sahip/"):
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), "--percent")

    def test_owner_and_voters_do_get_them(self):
        self.client.force_login(self.author)
        self.assertContains(self.client.get(self.url), "--percent: 100%")
        voter = self.client_class()
        voter.post(reverse("polls:vote", args=[self.poll.pk]), {"option_id": self.sinema.pk})
        self.assertContains(voter.get(self.url), "--percent: 100%")


class VoterCookieTests(TestCase):
    def setUp(self):
        self.poll = make_poll(make_user("sahip"))

    def test_anonymous_visitor_gets_the_cookie_together_with_the_vote_forms(self):
        for url in ("/", self.poll.get_absolute_url(), "/u/sahip/"):
            with self.subTest(url=url):
                cookie = self.client_class().get(url).cookies[COOKIE_NAME]
                self.assertTrue(cookie["httponly"])
                self.assertEqual(cookie["samesite"], "Lax")

    def test_cookie_is_not_issued_again(self):
        self.client.get("/")
        self.assertNotIn(COOKIE_NAME, self.client.get("/").cookies)

    def test_members_do_not_get_the_cookie(self):
        self.client.force_login(make_user("uye"))
        self.assertNotIn(COOKIE_NAME, self.client.get("/").cookies)

    def test_the_first_vote_uses_the_token_from_the_page_view(self):
        """Two requests racing before any cookie exists must share one token, so one of them gets a 409."""
        self.client.get(self.poll.get_absolute_url())
        request = RequestFactory().get("/")
        request.COOKIES[COOKIE_NAME] = self.client.cookies[COOKIE_NAME].value
        token = get_voter_token(request)

        option = self.poll.options.first()
        url = reverse("polls:vote", args=[self.poll.pk])
        statuses = [self.client.post(url, {"option_id": option.pk}).status_code for _ in range(2)]
        self.assertEqual(statuses, [302, 302])  # without JS: redirect with a message either way
        self.assertEqual(list(Vote.objects.values_list("voter_token", flat=True)), [token])


class MemberAfterAnonymousVoteTests(TestCase):
    """Logging in must not give the same browser a second vote on a poll it already voted on."""

    def setUp(self):
        self.poll = make_poll(make_user("sahip"), options=("Sinema", "Restoran"))
        self.sinema, self.restoran = self.poll.options.all()
        self.url = reverse("polls:vote", args=[self.poll.pk])
        self.client.post(self.url, {"option_id": self.sinema.pk})  # anonymous vote, cookie stored
        self.member = make_user("uye")

    def test_member_in_the_same_browser_cannot_vote_again(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url, {"option_id": self.restoran.pk}, headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["voted_option_id"], self.sinema.pk)
        self.assertEqual(Vote.objects.count(), 1)

    def test_card_shows_the_earlier_vote(self):
        self.client.force_login(self.member)
        page = self.client.get(self.poll.get_absolute_url())
        self.assertNotContains(page, 'name="option_id"')
        self.assertContains(page, "option--chosen")

    def test_member_in_another_browser_is_unaffected(self):
        other = self.client_class()
        other.force_login(self.member)
        response = other.post(self.url, {"option_id": self.restoran.pk}, headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 200)

    def test_members_own_vote_wins_over_the_anonymous_one_on_the_card(self):
        other = self.client_class()
        other.force_login(self.member)
        other.post(self.url, {"option_id": self.restoran.pk})
        other.cookies[COOKIE_NAME] = self.client.cookies[COOKIE_NAME].value
        page = other.get(self.poll.get_absolute_url())
        self.assertEqual(page.context["poll"].voted_option_id, self.restoran.pk)


@override_settings(THROTTLE_ENABLED=True)
class VoteThrottleTests(TestCase):
    def setUp(self):
        author = make_user("sahip")
        self.polls = [make_poll(author, question=f"Anket numarası {i}") for i in range(3)]

    def vote(self, poll, client=None):
        return (client or self.client_class()).post(
            reverse("polls:vote", args=[poll.pk]),
            {"option_id": poll.options.first().pk},
            headers={"Accept": "application/json"},
        )

    @override_settings(THROTTLE_LIMITS=limits(vote=(2, 600)))
    def test_anonymous_visitors_share_a_per_ip_limit(self):
        responses = [self.vote(poll) for poll in self.polls]
        self.assertEqual([r.status_code for r in responses], [200, 200, 429])
        self.assertEqual(responses[2].json()["ok"], False)
        self.assertNotIn(COOKIE_NAME, responses[2].cookies)
        self.assertEqual(Vote.objects.count(), 2)

    @override_settings(THROTTLE_LIMITS=limits(vote=(2, 600)))
    def test_members_are_counted_per_account_not_per_ip(self):
        first, second = self.client_class(), self.client_class()
        first.force_login(make_user("bir"))
        second.force_login(make_user("iki"))
        self.assertEqual([self.vote(p, first).status_code for p in self.polls], [200, 200, 429])
        self.assertEqual(self.vote(self.polls[0], second).status_code, 200)

    @override_settings(THROTTLE_LIMITS=limits(**{"vote-poll": (1, 3600)}))
    def test_limit_per_poll(self):
        self.assertEqual(self.vote(self.polls[0]).status_code, 200)
        self.assertEqual(self.vote(self.polls[0]).status_code, 429)
        self.assertEqual(self.vote(self.polls[1]).status_code, 200)


@override_settings(THROTTLE_ENABLED=True, THROTTLE_LIMITS=limits(**{"poll-create": (2, 3600)}))
class PollCreateThrottleTests(TestCase):
    def test_members_can_only_open_so_many_polls_per_hour(self):
        self.client.force_login(make_user())
        statuses = [self.client.post(CREATE_URL, poll_data(question=f"Anket numarası {i}")).status_code for i in range(3)]
        self.assertEqual(statuses, [302, 302, 429])
        self.assertEqual(Poll.objects.count(), 2)

    def test_anonymous_visitors_are_sent_to_login_without_using_up_the_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post(CREATE_URL, poll_data()).status_code, 302)


class PollCreateDoubleSubmitTests(TestCase):
    def test_the_same_question_twice_in_a_row_is_one_poll(self):
        self.client.force_login(make_user())
        first = self.client.post(CREATE_URL, poll_data(question="Çift tıklanan anket"))
        second = self.client.post(CREATE_URL, poll_data(question="Çift tıklanan anket"))
        self.assertEqual(Poll.objects.count(), 1)
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(Option.objects.count(), 2)

    def test_same_question_from_another_member_is_a_new_poll(self):
        self.client.force_login(make_user("bir"))
        self.client.post(CREATE_URL, poll_data(question="Aynı soru"))
        self.client.force_login(make_user("iki"))
        self.client.post(CREATE_URL, poll_data(question="Aynı soru"))
        self.assertEqual(Poll.objects.count(), 2)
