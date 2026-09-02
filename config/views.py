from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            from projects.models import Membership, Project

            project_ids = Membership.objects.filter(user=self.request.user).values_list(
                'project_id', flat=True
            )
            owned_ids = Project.objects.filter(owner=self.request.user).values_list('id', flat=True)
            project_ids = list(set(project_ids) | set(owned_ids))
            context['projects'] = Project.objects.filter(id__in=project_ids).order_by('-created_at')
        return context
