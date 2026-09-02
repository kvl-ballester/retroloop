from django.conf import settings
from django.db import models


class FeedbackCycle(models.Model):
    class Status(models.TextChoices):
        COLLECTING = 'COLLECTING', 'Collecting'
        CLOSED = 'CLOSED', 'Closed'

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='cycles')
    week_start = models.DateField()
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    facilitator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='facilitated_cycles',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLLECTING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start']

    def __str__(self):
        return f'{self.project.name} week of {self.week_start}'

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED


class CycleParticipation(models.Model):
    cycle = models.ForeignKey(
        FeedbackCycle, on_delete=models.CASCADE, related_name='participations'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cycle_participations',
    )
    card_count = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('cycle', 'user')

    def __str__(self):
        return f'{self.user.username} in cycle {self.cycle_id}'


class Card(models.Model):
    class Category(models.TextChoices):
        START = 'START', 'Start'
        STOP = 'STOP', 'Stop'
        CONTINUE = 'CONTINUE', 'Continue'

    cycle = models.ForeignKey(FeedbackCycle, on_delete=models.CASCADE, related_name='cards')
    category = models.CharField(max_length=20, choices=Category.choices)
    text = models.TextField(max_length=1000)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='feedback_cards',
    )
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'created_at']

    def __str__(self):
        name = self.author.username if self.author else 'anonymous'
        return f'{self.get_category_display()} card by {name}'
