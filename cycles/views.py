from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from projects.models import Project
from projects.permissions import can_facilitate_cycle, is_facilitator

from .forms import FeedbackCycleForm
from .models import FeedbackCycle


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
