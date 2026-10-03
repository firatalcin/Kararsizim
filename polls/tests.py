from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Option, Poll, Vote

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
