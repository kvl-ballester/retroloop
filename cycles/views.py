from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from projects.models import Project
from projects.permissions import (
    can_facilitate_cycle,
    can_submit_card,
    is_facilitator,
)

from .forms import CardForm, EditCardForm, FeedbackCycleForm
from .models import Card, CycleParticipation, FeedbackCycle


@login_required
@require_http_methods(['GET', 'POST'])
def create_cycle(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not is_facilitator(request.user, project):
        raise Http404('No Project matches the given query.')
    form = FeedbackCycleForm(request.POST or None, project=project)
    if request.method == 'POST':
        # Validate before allowing creation so an already-open cycle is
        # rejected server-side.
        if project.cycles.filter(status=FeedbackCycle.Status.COLLECTING).exists():
            form.add_error(
                None,
                'Start a cycle is already collecting; close it before opening a new one.',
            )
        elif form.is_valid():
            cycle = form.save(commit=False)
            cycle.project = project
            if cycle.facilitator_id is None:
                cycle.facilitator = project.owner
            cycle.save()
            return redirect('project_detail', project_id=project.id)
    return render(request, 'cycles/cycle_form.html', {'form': form, 'project': project})


@login_required
@require_http_methods(['POST'])
def close_cycle(request, project_id, cycle_id):
    project = get_object_or_404(Project, id=project_id)
    cycle = get_object_or_404(FeedbackCycle, id=cycle_id, project=project)
    if not can_facilitate_cycle(request.user, cycle):
        raise Http404('No Project matches the given query.')
    if cycle.status == FeedbackCycle.Status.COLLECTING:
        cycle.status = FeedbackCycle.Status.CLOSED
        cycle.save(update_fields=['status'])
    return redirect('project_detail', project_id=project.id)


def _rebuild_participation(cycle, user):
    """Create or sync the user's CycleParticipation row for a cycle.

    Must be called inside the same transaction as the card write so the count
    never drifts from the actual cards.
    """
    participation, _ = CycleParticipation.objects.get_or_create(cycle=cycle, user=user)
    participation.card_count = cycle.cards.filter(author=user).count()
    if participation.submitted_at is None and participation.card_count > 0:
        participation.submitted_at = timezone.now()
    participation.save()


def _own_card(cycle, user, card_id):
    return get_object_or_404(Card, id=card_id, cycle=cycle, author=user)


@login_required
@require_http_methods(['GET', 'POST'])
def feedback_form(request, cycle_id):
    cycle = get_object_or_404(FeedbackCycle, id=cycle_id)
    if not can_submit_card(request.user, cycle):
        raise Http404('No Cycle matches the given query.')
    collecting = cycle.status == FeedbackCycle.Status.COLLECTING
    own_cards = cycle.cards.filter(author=request.user).order_by('position', 'created_at')

    forms = {}
    for choice in Card.Category:
        posted = request.method == 'POST' and request.POST.get('category') == choice.value
        data = request.POST if posted else None
        forms[choice.value] = CardForm(data, initial={'category': choice.value})
        if posted and collecting and forms[choice.value].is_valid():
            with transaction.atomic():
                card = forms[choice.value].save(commit=False)
                card.cycle = cycle
                card.author = request.user
                card.position = (cycle.cards.aggregate(m=Max('position'))['m'] or 0) + 1
                card.save()
                _rebuild_participation(cycle, request.user)
            return redirect('feedback', cycle_id=cycle.id)

    own_cards = list(own_cards)
    order = (
        Card.Category.START.value,
        Card.Category.STOP.value,
        Card.Category.CONTINUE.value,
    )
    sections = []
    for category in order:
        cards = [c for c in own_cards if c.category == category]
        sections.append({'category': category, 'cards': cards, 'form': forms[category]})
    return render(
        request,
        'cycles/feedback_form.html',
        {
            'cycle': cycle,
            'project': cycle.project,
            'collecting': collecting,
            'sections': sections,
        },
    )


@login_required
@require_http_methods(['POST'])
def edit_card(request, cycle_id, card_id):
    cycle = get_object_or_404(FeedbackCycle, id=cycle_id)
    if not can_submit_card(request.user, cycle):
        raise Http404('No Cycle matches the given query.')
    if cycle.status != FeedbackCycle.Status.COLLECTING:
        raise Http404('No Cycle matches the given query.')
    card = _own_card(cycle, request.user, card_id)
    form = EditCardForm(request.POST, instance=card)
    if form.is_valid():
        with transaction.atomic():
            form.save()
            _rebuild_participation(cycle, request.user)
    return redirect('feedback', cycle_id=cycle.id)


@login_required
@require_http_methods(['POST'])
def delete_card(request, cycle_id, card_id):
    cycle = get_object_or_404(FeedbackCycle, id=cycle_id)
    if not can_submit_card(request.user, cycle):
        raise Http404('No Cycle matches the given query.')
    if cycle.status != FeedbackCycle.Status.COLLECTING:
        raise Http404('No Cycle matches the given query.')
    card = _own_card(cycle, request.user, card_id)
    with transaction.atomic():
        card.delete()
        _rebuild_participation(cycle, request.user)
    return redirect('feedback', cycle_id=cycle.id)
