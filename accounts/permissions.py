from rest_framework.permissions import BasePermission

from .models import UserRole


def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserRole.ADMIN
    profile = getattr(user, "userprofile", None)
    return profile.role if profile else None


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return get_role(request.user) == UserRole.ADMIN


class IsMentorOrManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return get_role(request.user) in {UserRole.MENTOR, UserRole.MANAGER, UserRole.ADMIN}


class IsHRManagerMentorAdmin(BasePermission):
    def has_permission(self, request, view):
        return get_role(request.user) in {UserRole.HR, UserRole.MANAGER, UserRole.MENTOR, UserRole.ADMIN}
