from django.db.models import Q

from accounts.models import UserRole
from accounts.permissions import get_role

from .models import DependencyStatus, DailyProgressEntry, InternProfile, MasterDataItem, WorkflowState


def calculate_completion_status_label(percentage: int) -> str:
    if percentage == 0:
        return "Not Started"
    if 1 <= percentage <= 30:
        return "Initiated"
    if 31 <= percentage <= 70:
        return "In Progress"
    if 71 <= percentage <= 99:
        return "Near Completion"
    return "Completed"


def resolve_completion_status_item(percentage: int):
    label = calculate_completion_status_label(percentage)
    return MasterDataItem.objects.filter(list_ref__name="Completion Status", value=label, is_active=True).first()


def is_entry_on_hold(entry: DailyProgressEntry) -> bool:
    return entry.blocker_flag or entry.dependencies.filter(dependency_status=DependencyStatus.OPEN).exists()


def can_view_entry(user, entry: DailyProgressEntry) -> bool:
    role = get_role(user)
    if role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.MENTOR}:
        return True
    if role == UserRole.HR:
        return True
    if role == UserRole.INTERN:
        return entry.intern_profile.user_id == user.id
    return False


def can_edit_entry(user, entry: DailyProgressEntry) -> bool:
    role = get_role(user)
    if role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.MENTOR}:
        return True
    if role == UserRole.INTERN:
        return entry.intern_profile.user_id == user.id
    return False


def visible_entries_for_user(user):
    role = get_role(user)
    qs = DailyProgressEntry.objects.select_related(
        "intern_profile__user",
        "project",
        "priority",
        "final_owner",
    ).prefetch_related("dependencies")

    if role in {UserRole.ADMIN, UserRole.MANAGER, UserRole.MENTOR, UserRole.HR}:
        return qs

    if role == UserRole.INTERN:
        intern = InternProfile.objects.filter(user=user).first()
        return qs.filter(intern_profile=intern) if intern else qs.none()

    return qs.none()


def apply_workflow_action(entry: DailyProgressEntry, action: str, actor):
    role = get_role(actor)

    if action == WorkflowState.REOPENED and role in {UserRole.MENTOR, UserRole.MANAGER, UserRole.ADMIN}:
        entry.workflow_state = WorkflowState.REOPENED
        return entry

    if role == UserRole.INTERN and entry.intern_profile.user_id == actor.id:
        # Intern can update workflow state on own entries in Phase 1.
        entry.workflow_state = action
        return entry

    if role in {UserRole.MENTOR, UserRole.MANAGER, UserRole.ADMIN}:
        entry.workflow_state = action
        return entry

    raise PermissionError("You are not allowed to perform this workflow action")
