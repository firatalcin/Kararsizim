from django.contrib import admin

from .models import Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "created_at")
    search_fields = ("question", "author__username")
    list_select_related = ("author",)
    inlines = [OptionInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "option", "user", "voter_token", "created_at")
    list_select_related = ("poll", "option", "user")
    raw_id_fields = ("poll", "option", "user")
