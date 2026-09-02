from django.contrib import admin

from .models import Retrospective


@admin.register(Retrospective)
class RetrospectiveAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'stage', 'versions', 'votes_per_member', 'started_at')
    list_filter = ('stage',)

    def versions(self, obj):
        return obj.version

    versions.short_description = 'version'
