"""Shared permission checks for branch staff actions."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

SALON_STAFF_ROLES = ("branch_admin", "staff")
KITCHEN_ROLES = ("branch_admin",)


def can_manage_branch(user, branch_id, roles=SALON_STAFF_ROLES):
    """True if the user is a superuser, or has one of `roles` for this branch."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "user_profile", None)
    if profile is None:
        return False
    return profile.role in roles and profile.branch_id == branch_id


def deny(request, message="Access denied. You do not have permission for this branch."):
    messages.error(request, message)
    return redirect("index")


def get_user_profile(user):
    """Return the user's profile or None (never raises)."""
    try:
        return user.user_profile
    except Exception:
        return None
