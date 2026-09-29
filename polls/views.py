from django.shortcuts import render


def home(request):
    # Temporary landing page; replaced by the poll feed in Phase 2.
    return render(request, "polls/home.html")
