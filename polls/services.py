from django.db import IntegrityError, transaction
from django.db.models import Count

from .models import Option, Vote
from .voter import get_voter_token


class InvalidOption(Exception):
    """The option doesn't exist or belongs to another poll."""


class AlreadyVoted(Exception):
    """This user/visitor already voted on the poll."""


def cast_vote(poll, option_id, user=None, voter_token=None):
    try:
        option = poll.options.get(pk=int(option_id))
    except (Option.DoesNotExist, TypeError, ValueError):
        raise InvalidOption

    try:
        # Savepoint: a unique-constraint failure must not poison an outer transaction.
        with transaction.atomic():
            return Vote.objects.create(poll=poll, option=option, user=user, voter_token=voter_token)
    except IntegrityError:
        raise AlreadyVoted


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
    """{poll_id: option_id} for the current member or cookie visitor, in a single query."""
    if request.user.is_authenticated:
        voter = {"user": request.user}
    else:
        token = get_voter_token(request)
        if not token:
            return {}
        voter = {"voter_token": token}
    poll_ids = [poll.pk for poll in polls]
    return dict(Vote.objects.filter(poll_id__in=poll_ids, **voter).values_list("poll_id", "option_id"))
