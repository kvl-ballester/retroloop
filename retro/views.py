from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_POST

from cycles.models import FeedbackCycle
from projects.permissions import can_facilitate, is_facilitator, is_member

from .models import Retrospective
from .serializers import serialize_state
from .services import advance_stage


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


@login_required
@require_POST
def advance(request, retro_id):
    retro = get_object_or_404(Retrospective, id=retro_id)
    if not is_member(request.user, retro.cycle.project):
        raise Http404('Not found.')
    if not can_facilitate(request.user, retro):
        raise PermissionDenied
    advance_stage(retro, request.user)
    return redirect('project_detail', project_id=retro.cycle.project_id)


@login_required
@require_GET
def state(request, retro_id):
    retro = get_object_or_404(Retrospective, id=retro_id)
    if not is_member(request.user, retro.cycle.project):
        raise Http404('Not found.')
    payload = serialize_state(retro, request.user)
    try:
        seen = int(request.GET.get('v', ''))
    except (TypeError, ValueError):
        seen = None
    if seen is not None and seen == retro.version:
        return HttpResponse(status=304)
    return JsonResponse(payload)
