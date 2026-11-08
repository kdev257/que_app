"""Business Workspace: owners and branch admins set up their organization, branches, services and menu."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from login.models import UserProfile
from organization.models import Branch, Service, Service_Name
from organization.permissions import (
    KITCHEN_ROLES, can_manage_branch, deny, get_user_profile, has_workspace, is_org_owner, workspace_branches,
)
from privacy.services import log_processing, record_consent
from restaurants.models import GlobalMenuItem, MenuCategory, MenuCategoryName, MenuItem
from reviews.forms import ReplyForm
from reviews.models import Review
from .forms import BranchForm, BusinessSignupForm, MenuItemForm, OrganizationForm, ServiceForm

ADMIN_ROLES = KITCHEN_ROLES  # branch_admin (owners and superusers are allowed by can_manage_branch)


def _is_restaurant(branch):
    return bool(branch.services_category and branch.services_category.name.lower() == "restaurant")


def _branch_or_deny(request, branch_id):
    """Return (branch, None) if the user may set up this branch, else (None, response)."""
    branch = get_object_or_404(Branch.objects.select_related("services_category", "organization"), id=branch_id)
    if not can_manage_branch(request.user, branch.id, ADMIN_ROLES):
        return None, deny(request)
    return branch, None


# ---------------------------------------------------------------------------
# Sign-up
# ---------------------------------------------------------------------------
def business_signup(request):
    """'List your business': create owner login + organization, then go to the workspace."""
    if request.user.is_authenticated and has_workspace(request.user):
        return redirect("workspace:home")
    if request.user.is_authenticated:
        messages.info(request, "You are logged in as a customer. Please log out to register a business account.")
        return redirect("index")

    if request.method == "POST":
        form = BusinessSignupForm(request.POST)
        if form.is_valid():
            from organization.models import Organization
            with transaction.atomic():
                user = form.save()
                org = Organization.objects.create(
                    name=form.cleaned_data["org_name"],
                    email=form.cleaned_data["org_email"],
                    phone=form.cleaned_data["org_phone"],
                )
                UserProfile.objects.create(
                    user=user, role="org_admin", organization=org,
                    phone_no=form.cleaned_data["phone"], address="", pin_code="",
                )
                record_consent(request, user=user, age_confirmed=True)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Welcome! Your business account is ready. Now add your first branch.")
            return redirect("workspace:branch_add")
    else:
        form = BusinessSignupForm()
    return render(request, "workspace/signup.html", {"form": form})


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
@login_required
def home(request):
    if not has_workspace(request.user):
        profile = get_user_profile(request.user)
        if profile and profile.role == "staff" and profile.branch_id:
            return redirect("shop_dashboard", id=profile.branch_id)
        messages.info(request, "The Business Workspace is for business owners. Register your business to get started.")
        return redirect("index")

    profile = get_user_profile(request.user)
    branches = (
        workspace_branches(request.user)
        .select_related("services_category", "organization")
        .annotate(
            service_count=Count("service_branch", filter=Q(service_branch__is_active=True), distinct=True),
            menu_count=Count("menu_categories__menu_items", distinct=True),
        )
        .order_by("organization__name", "name")
    )
    rows = []
    for b in branches:
        is_rest = _is_restaurant(b)
        steps = [
            ("Branch details", bool(b.address and b.pin_code and b.phone), "workspace:branch_edit"),
            ("Menu" if is_rest else "Services & rates", (b.menu_count if is_rest else b.service_count) > 0,
             "workspace:menu" if is_rest else "workspace:services"),
            ("Approved by QuickQueue", b.is_approved, None),
        ]
        rows.append({"branch": b, "is_restaurant": is_rest, "steps": steps,
                     "done": sum(1 for s in steps if s[1]), "total": len(steps)})

    return render(request, "workspace/home.html", {
        "organization": profile.organization if profile and profile.role == "org_admin" else None,
        "is_owner": is_org_owner(request.user),
        "rows": rows,
    })


@login_required
def org_edit(request):
    if not is_org_owner(request.user):
        return deny(request, "Only the business owner can edit the organization.")
    org = get_user_profile(request.user).organization
    form = OrganizationForm(request.POST or None, instance=org)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Organization details saved.")
        return redirect("workspace:home")
    return render(request, "workspace/form_page.html", {
        "form": form, "title": "Organization details", "back_url": "workspace:home",
    })


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------
@login_required
def branch_add(request):
    if not is_org_owner(request.user):
        return deny(request, "Only the business owner can add branches.")
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.organization = get_user_profile(request.user).organization
        branch.is_approved = False
        branch.save()
        form.save_landmarks(branch)
        messages.success(request, f"Branch '{branch.name}' added. Now add your "
                                  f"{'menu' if _is_restaurant(branch) else 'services and rates'}. "
                                  f"It will be shown to customers after QuickQueue approves it.")
        return redirect("workspace:menu" if _is_restaurant(branch) else "workspace:services", branch_id=branch.id)
    return render(request, "workspace/form_page.html", {
        "form": form, "title": "Add a branch", "back_url": "workspace:home",
    })


@login_required
def branch_edit(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        form.save_landmarks(branch)
        messages.success(request, "Branch details saved.")
        return redirect("workspace:branch_edit", branch_id=branch.id)
    return render(request, "workspace/form_page.html", {
        "form": form, "title": "Branch details", "branch": branch, "active": "details",
        "is_restaurant": _is_restaurant(branch),
    })


# ---------------------------------------------------------------------------
# Services (salons and other service businesses)
# ---------------------------------------------------------------------------
def _save_service(branch, form, service=None):
    name_text = form.cleaned_data["service_name"]
    service_name = Service_Name.objects.filter(name__iexact=name_text).first()
    if service_name is None:
        service_name = Service_Name.objects.create(name=name_text.title())
    if service is None:
        service = Service.objects.filter(branch=branch, name=service_name).first() or Service(branch=branch)
    service.name = service_name
    service.category = branch.services_category
    service.description = form.cleaned_data["description"].strip()
    service.price = form.cleaned_data["price"]
    service.average_time_minutes = form.cleaned_data["average_time_minutes"]
    service.is_active = form.cleaned_data["is_active"]
    service.save()
    return service


@login_required
def services(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    if _is_restaurant(branch):
        return redirect("workspace:menu", branch_id=branch.id)

    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            svc = _save_service(branch, form)
            messages.success(request, f"Service '{svc.name}' saved.")
            return redirect("workspace:services", branch_id=branch.id)
    else:
        form = ServiceForm(initial={"is_active": True, "average_time_minutes": 15})

    from organization.service_styles import GROUPS, RULES
    services_qs = list(Service.objects.filter(branch=branch).select_related("name").order_by("-is_active", "name__name"))
    active_count = sum(1 for s in services_qs if s.is_active)
    return render(request, "workspace/services.html", {
        "branch": branch, "active": "services", "form": form,
        "services": services_qs,
        "active_count": active_count,
        "hidden_count": len(services_qs) - active_count,
        "icon_groups": GROUPS,
        # For the live icon preview in the add form (stored icons + the same naming rules)
        "name_styles": {str(pk): [icon, grp] for pk, icon, grp in Service_Name.objects.values_list("id", "icon", "icon_group")},
        "icon_rules": [[list(k), i, g] for k, i, g in RULES],
    })


@login_required
def service_edit(request, branch_id, service_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    service = get_object_or_404(Service, id=service_id, branch=branch)
    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            _save_service(branch, form, service=service)
            messages.success(request, "Service updated.")
            return redirect("workspace:services", branch_id=branch.id)
    else:
        form = ServiceForm(initial={
            "service_choice": str(service.name_id), "description": service.description, "price": service.price,
            "average_time_minutes": service.average_time_minutes, "is_active": service.is_active,
        })
    return render(request, "workspace/form_page.html", {
        "form": form, "title": f"Edit service: {service.name}", "branch": branch, "active": "services",
        "service_name_toggle": True,
    })


@login_required
@require_POST
def service_toggle(request, branch_id, service_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    service = get_object_or_404(Service, id=service_id, branch=branch)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    messages.success(request, f"'{service.name}' is now {'active' if service.is_active else 'hidden from customers'}.")
    return redirect("workspace:services", branch_id=branch.id)


# ---------------------------------------------------------------------------
# Menu (restaurants)
# ---------------------------------------------------------------------------
def _save_menu_item(branch, form, item=None):
    cat_text = form.cleaned_data["category_name"]
    cat_name = MenuCategoryName.objects.filter(name__iexact=cat_text).first() \
        or MenuCategoryName.objects.create(name=cat_text.title())
    category, _ = MenuCategory.objects.get_or_create(branch=branch, name=cat_name)

    item_text = form.cleaned_data["item_name"]
    global_item = GlobalMenuItem.objects.filter(name__iexact=item_text).first() \
        or GlobalMenuItem.objects.create(name=item_text.title(), is_veg=form.cleaned_data["is_veg"])

    if item is None:
        item = MenuItem.objects.filter(category__branch=branch, name=global_item).first() or MenuItem()
    item.category = category
    item.name = global_item
    item.description = form.cleaned_data["description"]
    item.price = form.cleaned_data["price"]
    item.preparation_time_minutes = form.cleaned_data["preparation_time_minutes"]
    item.is_veg = form.cleaned_data["is_veg"]
    item.is_available = form.cleaned_data["is_available"]
    item.save()
    return item


def _menu_lists():
    return {
        "category_names": MenuCategoryName.objects.order_by("name").values_list("name", flat=True),
        "item_names": GlobalMenuItem.objects.order_by("name").values_list("name", flat=True),
    }


@login_required
def menu(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    if not _is_restaurant(branch):
        return redirect("workspace:services", branch_id=branch.id)

    if request.method == "POST":
        form = MenuItemForm(request.POST)
        if form.is_valid():
            item = _save_menu_item(branch, form)
            messages.success(request, f"'{item.name.name}' saved.")
            return redirect("workspace:menu", branch_id=branch.id)
    else:
        form = MenuItemForm(initial={"is_veg": True, "is_available": True, "preparation_time_minutes": 15})

    categories = MenuCategory.objects.filter(branch=branch).select_related("name").prefetch_related("menu_items__name")
    return render(request, "workspace/menu.html", {
        "branch": branch, "active": "services", "form": form, "categories": categories, **_menu_lists(),
    })


@login_required
def menu_item_edit(request, branch_id, item_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    item = get_object_or_404(MenuItem.objects.select_related("name", "category__name"), id=item_id, category__branch=branch)
    if request.method == "POST":
        form = MenuItemForm(request.POST)
        if form.is_valid():
            _save_menu_item(branch, form, item=item)
            messages.success(request, "Menu item updated.")
            return redirect("workspace:menu", branch_id=branch.id)
    else:
        form = MenuItemForm(initial={
            "category_name": item.category.name.name, "item_name": item.name.name, "description": item.description,
            "price": item.price, "preparation_time_minutes": item.preparation_time_minutes,
            "is_veg": item.is_veg, "is_available": item.is_available,
        })
    return render(request, "workspace/form_page.html", {
        "form": form, "title": f"Edit item: {item.name.name}", "branch": branch, "active": "services",
        "is_restaurant": True, **_menu_lists(), "menu_datalists": True,
    })


@login_required
@require_POST
def menu_item_toggle(request, branch_id, item_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    item = get_object_or_404(MenuItem, id=item_id, category__branch=branch)
    item.is_available = not item.is_available
    item.save(update_fields=["is_available"])
    return redirect("workspace:menu", branch_id=branch.id)


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@login_required
def reviews(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    if request.method == "POST":
        review = get_object_or_404(Review, id=request.POST.get("review_id"), branch=branch)
        form = ReplyForm(request.POST)
        if form.is_valid():
            review.reply = form.cleaned_data["reply"]
            review.replied_at = timezone.now()
            review.save(update_fields=["reply", "replied_at"])
            messages.success(request, "Reply posted.")
        return redirect("workspace:reviews", branch_id=branch.id)
    return render(request, "workspace/reviews.html", {
        "branch": branch, "active": "reviews", "is_restaurant": _is_restaurant(branch),
        "reviews": Review.objects.filter(branch=branch).order_by("-created_at")[:200],
    })
