from .models import Membership


def is_member(user, project):
    """True when user is the project owner or holds a membership row."""
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(project=project, user=user).exists() or (
        project.owner_id == user.id
    )


def is_facilitator(user, project):
    """True when user owns the project or holds a FACILITATOR membership."""
    if not user or not user.is_authenticated:
        return False
    if project.owner_id == user.id:
        return True
    return Membership.objects.filter(
        project=project, user=user, role=Membership.Role.FACILITATOR
    ).exists()


def is_member_of_project(user, project):
    return is_member(user, project)


def is_facilitator_of_project(user, project):
    return is_facilitator(user, project)
