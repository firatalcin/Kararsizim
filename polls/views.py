from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OptionFormSet, PollForm
from .models import Option, Poll

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


def feed(request):
    page = Paginator(polls_with_counts(), POLLS_PER_PAGE).get_page(request.GET.get("sayfa"))
    return render(request, "polls/feed.html", {"page": page, "polls": page.object_list})


def poll_detail(request, pk):
    poll = get_object_or_404(polls_with_counts(), pk=pk)
    return render(request, "polls/detail.html", {"poll": poll})


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
