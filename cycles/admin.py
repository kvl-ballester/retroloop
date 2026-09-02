from django.contrib import admin

from .models import Card, CycleParticipation, FeedbackCycle


@admin.register(FeedbackCycle)
class FeedbackCycleAdmin(admin.ModelAdmin):
    list_display = ('project', 'week_start', 'facilitator', 'status', 'closes_at')
    list_filter = ('status',)


@admin.register(CycleParticipation)
class CycleParticipationAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'user', 'card_count', 'submitted_at')


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'category', 'author', 'is_anonymous', 'position')
    list_filter = ('category', 'is_anonymous')
