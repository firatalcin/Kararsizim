from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q

from .models import Option, Vote
from .voter import get_voter_token


class InvalidOption(Exception):
    """The option doesn't exist or belongs to another poll."""


class AlreadyVoted(Exception):
    """This user/visitor already voted on the poll."""


def _identity(user=None, voter_token=None):
    """Q matching the votes of a member and/or an anonymous browser; None if there is neither."""
    query = None
    if user is not None:
        query = Q(user=user)
    if voter_token:
        query = (query | Q(voter_token=voter_token)) if query else Q(voter_token=voter_token)
    return query


def cast_vote(poll, option_id, user=None, voter_token=None, browser_token=None):
    """Record a vote. `browser_token` is the browser's voter cookie when a *member* votes: a vote
    already cast anonymously from this browser counts as theirs, so logging in is not a second vote."""
    try:
        option = poll.options.get(pk=int(option_id))
    except (Option.DoesNotExist, TypeError, ValueError):
        raise InvalidOption

    if user is not None and browser_token and Vote.objects.filter(poll=poll, voter_token=browser_token).exists():
        raise AlreadyVoted

    try:
        # Savepoint: a unique-constraint failure must not poison an outer transaction.
        with transaction.atomic():
            return Vote.objects.create(poll=poll, option=option, user=user, voter_token=voter_token)
    except IntegrityError:
        raise AlreadyVoted


def find_vote_option(poll, user=None, voter_token=None):
    """The option this member/browser voted for on `poll` (the member's own vote first), or None."""
    identity = _identity(user, voter_token)
    if identity is None:
        return None
    return (
        Vote.objects.filter(identity, poll=poll)
        .order_by(F("user_id").asc(nulls_last=True))
        .values_list("option_id", flat=True)
        .first()
    )


def percentages(counts):
    """Whole-number percentages that sum to exactly 100 (largest remainder method); all 0 if no votes."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    exact = [count * 100 / total for count in counts]
    result = [int(value) for value in exact]
    # Hand the leftover points to the largest fractional parts (earlier options win ties).
    by_remainder = sorted(range(len(counts)), key=lambda i: exact[i] - result[i], reverse=True)
    for i in by_remainder[: 100 - sum(result)]:
        result[i] += 1
    return result


def build_results(poll):
    """Vote results in the JSON shape of the vote endpoint (no personal data)."""
    options = list(poll.options.annotate(vote_count=Count("votes")).order_by("position"))
    counts = [option.vote_count for option in options]
    return {
        "poll_id": poll.pk,
        "total_votes": sum(counts),
        "options": [
            {"id": option.pk, "text": option.text, "votes": option.vote_count, "percent": percent}
            for option, percent in zip(options, percentages(counts))
        ],
    }


def get_user_votes(polls, request):
    """{poll_id: option_id} for the current member or cookie visitor, in a single query.

    A member also gets the votes this browser cast anonymously (before logging in); their own
    votes win if both exist.
    """
    user = request.user if request.user.is_authenticated else None
    identity = _identity(user, get_voter_token(request))
    if identity is None:
        return {}
    poll_ids = [poll.pk for poll in polls]
    rows = (
        Vote.objects.filter(identity, poll_id__in=poll_ids)
        .order_by(F("user_id").asc(nulls_first=True))  # anonymous rows first, so member rows overwrite them
        .values_list("poll_id", "option_id")
    )
    return dict(rows)
