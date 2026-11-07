from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BranchGSTForm
from .models import Branch
from .permissions import KITCHEN_ROLES, can_manage_branch, deny


@login_required
def branch_gst_settings(request, branch_id):
    """Branch admin can set GST registration, GSTIN, GST % and price-includes-GST."""
    branch = get_object_or_404(Branch, id=branch_id)
    if not can_manage_branch(request.user, branch.id, KITCHEN_ROLES):  # branch_admin or superuser
        return deny(request)

    if request.method == "POST":
        form = BranchGSTForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, "GST settings saved. New invoices will use these settings.")
            return redirect("shop_dashboard", id=branch.id)
    else:
        form = BranchGSTForm(instance=branch)

    return render(request, "organization/gst_settings.html", {"form": form, "branch": branch})
