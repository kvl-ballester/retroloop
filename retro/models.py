from django.db import models


class Retrospective(models.Model):
    class Stage(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        REVEAL = 'REVEAL', 'Reveal'
        CLUSTER = 'CLUSTER', 'Cluster'
        VOTE = 'VOTE', 'Vote'
        DISCUSS = 'DISCUSS', 'Discuss'
        COMPLETE = 'COMPLETE', 'Complete'

    cycle = models.OneToOneField(
        'cycles.FeedbackCycle', on_delete=models.CASCADE, related_name='retrospective'
    )
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.DRAFT)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    votes_per_member = models.PositiveIntegerField(default=3)

    def __str__(self):
        return f'Retrospective for cycle {self.cycle_id}'
