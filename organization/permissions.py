"""Shared permission checks for branch / organization actions."""
from django.contrib import messages
from django.shortcuts import redirect

SALON_STAFF_ROLES = ("branch_admin", "staff")
KITCHEN_ROLES = ("branch_admin",)
WORKSPACE_ROLES = ("org_admin", "branch_admin")


def get_user_profile(user):
    """Return the user's profile or None (never raises)."""
    try:
        return user.user_profile
    except Exception:
        return None


def can_manage_branch(user, branch_id, roles=SALON_STAFF_ROLES):
    """
    True if the user may act on this branch:
    - superuser: always
    - organization owner (org_admin): any branch of their organization
    - other roles in `roles`: only their own branch
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = get_user_profile(user)
    if profile is None:
        return False
    if profile.role == "org_admin" and profile.organization_id:
        from .models import Branch
        return Branch.objects.filter(id=branch_id, organization_id=profile.organization_id).exists()
    return profile.role in roles and profile.branch_id == branch_id


def is_org_owner(user, organization_id=None):
    if not user.is_authenticated:
        return False
    profile = get_user_profile(user)
    if profile is None or profile.role != "org_admin" or not profile.organization_id:
        return False
    return organization_id is None or profile.organization_id == organization_id


def has_workspace(user):
    """Show the 'Business Workspace' link?"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = get_user_profile(user)
    return profile is not None and profile.role in WORKSPACE_ROLES


def workspace_branches(user):
    """Branches this user can set up in the workspace."""
    from .models import Branch
    if user.is_superuser:
        return Branch.objects.all()
    profile = get_user_profile(user)
    if profile is None:
        return Branch.objects.none()
    if profile.role == "org_admin" and profile.organization_id:
        return Branch.objects.filter(organization_id=profile.organization_id)
    if profile.role == "branch_admin" and profile.branch_id:
        return Branch.objects.filter(id=profile.branch_id)
    return Branch.objects.none()


BUSINESS_ROLES = ("org_admin", "branch_admin", "staff")


def is_restaurant_branch(branch):
    return bool(branch and branch.services_category_id and branch.services_category.name.lower() == "restaurant")


def home_url_for(user):
    """
    Where a user lands after login (one place for the rule):
      org_admin (owner)        -> Business Workspace
      branch_admin             -> their branch dashboard (kitchen for restaurants, shop for salons);
                                  workspace if no branch is linked yet
      staff                    -> their branch staff screen (restaurant staff screen or shop dashboard)
      superuser / site staff   -> Django admin
      no profile               -> profile page
      customer / anyone else   -> services page
    """
    from django.urls import reverse
    profile = get_user_profile(user)
    role = profile.role if profile else None
    branch = profile.branch if profile and profile.branch_id else None

    if role == "org_admin":
        return reverse("workspace:home")
    if role == "branch_admin":
        if branch is None:
            return reverse("workspace:home")
        if is_restaurant_branch(branch):
            return reverse("restaurants:kitchen_dashboard", args=[branch.id])
        return reverse("shop_dashboard", args=[branch.id])
    if role == "staff" and branch is not None:
        if is_restaurant_branch(branch):
            return reverse("restaurants:staff_dashboard", args=[branch.id])
        return reverse("shop_dashboard", args=[branch.id])
    if user.is_superuser or user.is_staff:
        return reverse("admin:index")
    if profile is None:
        return reverse("user_profile")
    return reverse("index")


def deny(request, message="Access denied. You do not have permission for this branch."):
    messages.error(request, message)
    return redirect("index")
