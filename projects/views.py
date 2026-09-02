from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import ProjectForm
from .models import Membership, Project
from .permissions import is_facilitator, is_member


def join_project(request, token):
    project = get_object_or_404(Project, join_token=token)
    if not request.user.is_authenticated:
        return redirect(f'{reverse("login")}?next={request.path}')
    if not is_member(request.user, project):
        Membership.objects.create(project=project, user=request.user)
    return redirect('project_detail', project_id=project.id)


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not is_member(request.user, project):
        raise Http404('No Project matches the given query.')
    memberships = Membership.objects.filter(project=project).select_related('user')
    cycles = project.cycles.all()
    current_cycle = cycles.filter(status='COLLECTING').first()
    past_cycles = [c for c in cycles if c.id != (current_cycle.id if current_cycle else None)]
    member_count = memberships.count()
    participation_count = current_cycle.participations.count() if current_cycle else 0
    return render(
        request,
        'projects/project_detail.html',
        {
            'project': project,
            'memberships': memberships,
            'membership_count': member_count,
            'can_facilitate': is_facilitator(request.user, project),
            'join_url': request.build_absolute_uri(
                reverse('join_project', kwargs={'token': project.join_token})
            ),
            'current_cycle': current_cycle,
            'participation_count': participation_count,
            'past_cycles': past_cycles,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def create_project(request):
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        Membership.objects.create(
            project=project, user=request.user, role=Membership.Role.FACILITATOR
        )
        return redirect('project_detail', project_id=project.id)
    return render(request, 'projects/project_form.html', {'form': form})


@login_required
@require_http_methods(['POST'])
def rotate_join_link(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not is_facilitator(request.user, project):
        raise Http404('No Project matches the given query.')
    project.rotate_join_token()
    return redirect('project_detail', project_id=project.id)
