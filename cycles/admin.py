from django.contrib import admin

from .models import CycleParticipation, FeedbackCycle


@admin.register(FeedbackCycle)
class FeedbackCycleAdmin(admin.ModelAdmin):
    list_display = ('project', 'week_start', 'facilitator', 'status', 'closes_at')
    list_filter = ('status',)


@admin.register(CycleParticipation)
class CycleParticipationAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'user', 'card_count', 'submitted_at')
