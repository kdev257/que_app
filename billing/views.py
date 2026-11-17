from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from organization.models import Branch
from organization.permissions import KITCHEN_ROLES, SALON_STAFF_ROLES, can_manage_branch, deny
from queues.views import get_guest
from privacy.services import log_processing
from .models import CreditNote, Invoice


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
    can_credit = request.user.is_authenticated and can_manage_branch(request.user, invoice.branch_id, KITCHEN_ROLES)
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "items": invoice.items.all(),
        "is_staff_view": is_staff_view,
        "can_credit": can_credit,
        "credit_notes": invoice.credit_notes.all(),
        "payment_modes": Invoice.PAYMENT_MODE_CHOICES,
        "credit_reasons": CreditNote.REASON_CHOICES,
    })


@login_required
@require_POST
def set_payment_mode(request, invoice_id):
    """Staff record how the bill was paid (cash / UPI / card ...)."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if not can_manage_branch(request.user, invoice.branch_id, SALON_STAFF_ROLES):
        return deny(request)
    mode = request.POST.get("payment_mode", "")
    if mode in dict(Invoice.PAYMENT_MODE_CHOICES):
        Invoice.objects.filter(pk=invoice.pk).update(payment_mode=mode)
        messages.success(request, f"Payment mode saved: {dict(Invoice.PAYMENT_MODE_CHOICES)[mode]}.")
    return redirect("billing:invoice_detail", invoice_id=invoice.id)


@login_required
@require_POST
def credit_note_create(request, invoice_id):
    """Branch admin / owner: issue a credit note (refund or cancel) against an invoice."""
    from decimal import Decimal, InvalidOperation
    from .services import create_credit_note
    invoice = get_object_or_404(Invoice.objects.select_related("branch"), id=invoice_id)
    if not can_manage_branch(request.user, invoice.branch_id, KITCHEN_ROLES):
        return deny(request, "Only the branch admin or owner can issue a credit note.")
    reason = request.POST.get("reason", "")
    if reason not in dict(CreditNote.REASON_CHOICES):
        messages.error(request, "Please choose a reason.")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)
    try:
        amount = Decimal(request.POST.get("amount") or "0")
        note = create_credit_note(invoice, amount, reason, request.POST.get("note", "").strip(), request.user)
    except (InvalidOperation, ValueError) as exc:
        messages.error(request, f"Credit note not made. {exc}")
        return redirect("billing:invoice_detail", invoice_id=invoice.id)
    messages.success(request, f"Credit note {note.number} made for Rs. {note.total_amount}.")
    return redirect("billing:credit_note_detail", credit_note_id=note.id)


def credit_note_detail(request, credit_note_id):
    note = get_object_or_404(CreditNote.objects.select_related("invoice", "branch"), id=credit_note_id)
    if not _can_view_invoice(request, note.invoice):
        messages.error(request, "You are not authorized to view this credit note.")
        return redirect("index")
    return render(request, "billing/credit_note_detail.html", {"note": note, "invoice": note.invoice})


@login_required
def branch_invoices(request, branch_id):
    """List of invoices for one branch (staff only)."""
    branch = get_object_or_404(Branch, id=branch_id)
    if not can_manage_branch(request.user, branch.id, SALON_STAFF_ROLES):
        return deny(request)
    invoices = Invoice.objects.filter(branch=branch).order_by("-created_at")[:200]
    return render(request, "billing/branch_invoices.html", {"branch": branch, "invoices": invoices})
