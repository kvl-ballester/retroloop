from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from cycles.models import FeedbackCycle
from projects.permissions import is_facilitator, is_member

from .models import Retrospective


@login_required
@require_POST
def create_retro(request, project_id, cycle_id):
    cycle = get_object_or_404(FeedbackCycle, id=cycle_id, project_id=project_id)
    if not is_member(request.user, cycle.project):
        raise Http404('Not found.')
    if not (is_facilitator(request.user, cycle.project) or cycle.facilitator_id == request.user.id):
        raise PermissionDenied
    if cycle.status != FeedbackCycle.Status.CLOSED:
        raise Http404('Not found.')
    if not Retrospective.objects.filter(cycle=cycle).exists():
        Retrospective.objects.create(cycle=cycle)
    return redirect('project_detail', project_id=project_id)
