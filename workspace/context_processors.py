from organization.permissions import has_workspace


def workspace_nav(request):
    """Show the 'Business Workspace' link in the top menu for business users."""
    user = getattr(request, "user", None)
    return {"HAS_WORKSPACE": bool(user and has_workspace(user))}
