from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.views import get_safe_next_url

from .forms import OptionFormSet, PollForm
from .models import Option, Poll, Vote
from .services import AlreadyVoted, InvalidOption, build_results, cast_vote, get_user_votes, percentages
from .voter import ensure_voter_token, set_voter_cookie

POLLS_PER_PAGE = 20


def polls_with_counts():
    """Polls with author, total votes and per-option vote counts in a fixed number of queries."""
    return (
        Poll.objects.select_related("author")
        .annotate(total_votes=Count("votes"))
        .prefetch_related(Prefetch("options", queryset=Option.objects.annotate(vote_count=Count("votes")).order_by("position")))
        # Meta.ordering is ignored once the query has a GROUP BY, so order explicitly.
        .order_by("-created_at", "-pk")
    )


def prepare_cards(polls, request):
    """Attach the viewer's vote state and option percentages that _poll_card.html needs."""
    user_votes = get_user_votes(polls, request)
    for poll in polls:
        poll.voted_option_id = user_votes.get(poll.pk)
        poll.can_vote = poll.voted_option_id is None
        poll.is_owner = request.user.is_authenticated and poll.author_id == request.user.pk
        # Results stay hidden until you vote (no bias), except for the poll's owner.
        poll.show_results = not poll.can_vote or poll.is_owner
        options = list(poll.options.all())
        for option, percent in zip(options, percentages([o.vote_count for o in options])):
            option.percent = percent
    return polls


def feed(request):
    page = Paginator(polls_with_counts(), POLLS_PER_PAGE).get_page(request.GET.get("sayfa"))
    polls = prepare_cards(list(page.object_list), request)
    return render(request, "polls/feed.html", {"page": page, "polls": polls})


def poll_detail(request, pk):
    poll = get_object_or_404(polls_with_counts(), pk=pk)
    prepare_cards([poll], request)
    return render(request, "polls/detail.html", {"poll": poll})


@require_POST
def poll_vote(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    wants_json = "application/json" in request.headers.get("Accept", "")

    if request.user.is_authenticated:
        voter = {"user": request.user}
        token_is_new = False
    else:
        token, token_is_new = ensure_voter_token(request)
        voter = {"voter_token": token}

    try:
        vote = cast_vote(poll, request.POST.get("option_id"), **voter)
    except InvalidOption:
        status, error, voted_option_id = 400, "Geçersiz seçenek.", None
    except AlreadyVoted:
        status, error = 409, "Bu ankete zaten oy verdin."
        voted_option_id = Vote.objects.filter(poll=poll, **voter).values_list("option_id", flat=True).first()
    else:
        status, error, voted_option_id = 200, None, vote.option_id

    if wants_json:
        payload = {"ok": status == 200}
        if error:
            payload["error"] = error
        if status != 400:
            payload.update(build_results(poll), voted_option_id=voted_option_id)
        response = JsonResponse(payload, status=status)
    else:
        if error:
            messages.error(request, error)
        else:
            messages.success(request, "Oyun kaydedildi! ✨")
        next_url = get_safe_next_url(request) or poll.get_absolute_url()
        response = redirect(f"{next_url}#anket-{poll.pk}")

    if status == 200 and token_is_new:
        set_voter_cookie(response, voter["voter_token"])
    return response


@login_required
def poll_create(request):
    if request.method == "POST":
        form = PollForm(request.POST)
        formset = OptionFormSet(request.POST, prefix="options")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                poll = form.save(commit=False)
                poll.author = request.user
                poll.save()
                Option.objects.bulk_create(
                    Option(poll=poll, text=text, position=position)
                    for position, text in enumerate(formset.option_texts())
                )
            messages.success(request, "Anketin yayında! 🎉")
            return redirect(poll)
    else:
        form = PollForm()
        formset = OptionFormSet(prefix="options")

    return render(request, "polls/create.html", {"form": form, "formset": formset})


@login_required
def poll_delete(request, pk):
    # Only the author may delete; everyone else gets a 404 (the poll's existence isn't confirmed).
    poll = get_object_or_404(Poll, pk=pk, author=request.user)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anket silindi.")
        return redirect("polls:feed")
    return render(request, "polls/confirm_delete.html", {"poll": poll})
