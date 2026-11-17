from organization.permissions import has_workspace, workspace_branches


def workspace_nav(request):
    """Top-bar 'Business' menu for owners, branch admins and superusers: their branches and quick links."""
    user = getattr(request, "user", None)
    if not (user and has_workspace(user)):
        return {"HAS_WORKSPACE": False, "BUSINESS_BRANCHES": []}
    branches = [
        {"id": b.id, "name": b.name,
         "is_restaurant": bool(b.services_category_id and b.services_category.name.lower() == "restaurant")}
        for b in workspace_branches(user).select_related("services_category").order_by("name")[:20]
    ]
    return {"HAS_WORKSPACE": True, "BUSINESS_BRANCHES": branches}
