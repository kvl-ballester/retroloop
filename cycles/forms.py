from datetime import datetime, timedelta

from django import forms

from .models import FeedbackCycle


class FeedbackCycleForm(forms.ModelForm):
    class Meta:
        model = FeedbackCycle
        fields = ['week_start', 'opens_at', 'closes_at', 'facilitator']
        widgets = {
            'week_start': forms.DateInput(attrs={'type': 'date'}),
            'opens_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'closes_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        now = datetime.now()
        monday = now.date() - timedelta(days=now.weekday())
        self.fields['week_start'].initial = monday
        self.fields['opens_at'].initial = now
        self.fields['closes_at'].initial = now + timedelta(days=7)
        self.fields['facilitator'].required = False
        if project is not None:
            from django.contrib.auth.models import User

            from projects.models import Membership

            member_ids = Membership.objects.filter(project=project).values_list(
                'user_id', flat=True
            )
            self.fields['facilitator'].queryset = User.objects.filter(id__in=member_ids)
            self.initial['facilitator'] = project.owner_id

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('opens_at') and cleaned.get('closes_at'):
            if cleaned['closes_at'] <= cleaned['opens_at']:
                self.add_error('closes_at', 'Closes must be after it opens.')
        return cleaned
