from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from organization.models import Branch
from organization.permissions import can_manage_branch, deny, SALON_STAFF_ROLES
from queues.views import get_guest
from privacy.services import log_processing
from .models import Invoice


INVOICE_LINK_SALT = "billing.invoice"
INVOICE_LINK_DAYS = 90


def invoice_link_key(invoice):
    from django.core import signing
    return signing.dumps(invoice.id, salt=INVOICE_LINK_SALT)


def _key_ok(request, invoice):
    from django.core import signing
    key = request.GET.get("k")
    if not key:
        return False
    try:
        return signing.loads(key, salt=INVOICE_LINK_SALT, max_age=INVOICE_LINK_DAYS * 24 * 3600) == invoice.id
    except signing.BadSignature:
        return False


def _can_view_invoice(request, invoice):
    if _key_ok(request, invoice):  # signed link from the invoice email
        return True
    user = request.user
    if user.is_authenticated:
        if invoice.customer_user_id == user.id:
            return True
        return can_manage_branch(user, invoice.branch_id, SALON_STAFF_ROLES)
    guest = get_guest(request)
    return guest is not None and invoice.customer_guest_id == guest.id


def invoice_detail(request, invoice_id):
    """Printable invoice page. Staff of the branch, the customer, or the guest can view it."""
    invoice = get_object_or_404(Invoice.objects.select_related("branch"), id=invoice_id)
    if not _can_view_invoice(request, invoice):
        messages.error(request, "You are not authorized to view this invoice.")
        return redirect("index")
    log_processing("invoice_viewed", request, subject_user=invoice.customer_user,
                   subject_guest=invoice.customer_guest, obj=invoice)
    is_staff_view = request.user.is_authenticated and can_manage_branch(
        request.user, invoice.branch_id, SALON_STAFF_ROLES
    )
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "items": invoice.items.all(),
        "is_staff_view": is_staff_view,
    })


@login_required
def branch_invoices(request, branch_id):
    """List of invoices for one branch (staff only)."""
    branch = get_object_or_404(Branch, id=branch_id)
    if not can_manage_branch(request.user, branch.id, SALON_STAFF_ROLES):
        return deny(request)
    invoices = Invoice.objects.filter(branch=branch).order_by("-created_at")[:200]
    return render(request, "billing/branch_invoices.html", {"branch": branch, "invoices": invoices})
