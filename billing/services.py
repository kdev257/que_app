"""Invoice creation and email. All amounts are calculated here once and stored."""
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from .models import Invoice, InvoiceItem

logger = logging.getLogger(__name__)
TWO_PLACES = Decimal("0.01")


def _money(value):
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _invoice_lines(token):
    """Return (source, [(description, qty, unit_price), ...]) for a token."""
    order = getattr(token, "restaurant_order", None) if hasattr(token, "restaurant_order") else None
    if order is not None:
        lines = [
            (item.menu_item.name.name, item.quantity, item.price)
            for item in order.items.select_related("menu_item__name")
        ]
        return "restaurant", lines

    from queues.models import TokenService
    lines = [
        (str(ts.service.name), 1, ts.service.price)
        for ts in TokenService.objects.filter(token=token).select_related("service__name")
    ]
    return "service", lines


def _customer_details(token):
    if token.user:
        user = token.user
        name = f"{user.first_name} {user.last_name}".strip() or user.username
        profile = getattr(user, "user_profile", None) if hasattr(user, "user_profile") else None
        phone = (profile.phone_no or "") if profile else ""
        return name, user.email or "", phone
    if token.guest:
        return token.guest.name, token.guest.email or "", token.guest.phone_no or ""
    return "Walk-in Customer", "", ""


def _seller_address(branch):
    parts = [branch.address, branch.locality, branch.city, branch.state, branch.pin_code]
    return ", ".join(p.strip() for p in parts if p and p.strip())


def _split_gst(amount, rate, inclusive):
    """Return (taxable, gst) for an amount at a GST rate."""
    if rate <= 0:
        return amount, Decimal("0.00")
    if inclusive:
        taxable = _money(amount * Decimal("100") / (Decimal("100") + rate))
        return taxable, amount - taxable
    return amount, _money(amount * rate / Decimal("100"))


def active_platform_fee():
    from accounts.models import PlatformFee
    fee = PlatformFee.objects.filter(is_active=True).first()
    return fee if (fee and fee.is_currently_active()) else None


def calculate_amounts(subtotal, discount, booking_fee, branch, fee_settings=None):
    """Pure calculation, returns a dict of all invoice amounts.
    fee_settings: the PlatformFee record (for GST on the booking fee), or None."""
    subtotal = _money(subtotal)
    discount = min(_money(discount), subtotal)
    booking_fee = _money(booking_fee)
    net = subtotal - discount

    gst_rate = _money(branch.gst_percentage) if branch.is_gst_registered else Decimal("0.00")
    taxable, gst = _split_gst(net, gst_rate, branch.prices_include_gst)

    # GST on the booking fee (platform setting)
    fee_rate = Decimal("0.00")
    fee_inclusive = True
    if fee_settings is not None and fee_settings.gst_on_fee and booking_fee > 0:
        fee_rate = _money(fee_settings.fee_gst_percentage)
        fee_inclusive = fee_settings.fee_includes_gst
    fee_taxable, fee_gst = _split_gst(booking_fee, fee_rate, fee_inclusive)

    cgst = _money(gst / 2)
    sgst = gst - cgst
    return {
        "subtotal": subtotal,
        "discount_amount": discount,
        "taxable_amount": taxable,
        "gst_percentage": gst_rate,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "gst_amount": gst,
        "booking_fee": fee_taxable,
        "booking_fee_gst_percentage": fee_rate,
        "booking_fee_gst_amount": fee_gst,
        "total_amount": taxable + gst + fee_taxable + fee_gst,
    }


def create_invoice_for_token(token, created_by=None):
    """Create (once) and return the invoice for a completed token."""
    existing = Invoice.objects.filter(token=token).first()
    if existing:
        return existing

    branch = token.branch
    source, lines = _invoice_lines(token)
    subtotal = sum((_money(price) * qty for _, qty, price in lines), Decimal("0.00"))
    fee_settings = active_platform_fee()
    amounts = calculate_amounts(subtotal, token.discount_amount, token.booking_fee, branch, fee_settings)
    customer_name, customer_email, customer_phone = _customer_details(token)

    try:
        with transaction.atomic():
            invoice = Invoice.objects.create(
                invoice_number=f"TMP-{uuid.uuid4().hex[:20]}",
                token=token,
                branch=branch,
                source=source,
                token_number=token.token_number,
                service_date=token.token_date,
                seller_name=f"{branch.name} - {branch.organization.name}",
                seller_address=_seller_address(branch),
                seller_phone=branch.phone or "",
                seller_email=branch.email or "",
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_user=token.user,
                customer_guest=token.guest,
                is_gst_invoice=branch.is_gst_registered,
                gstin=(branch.gstin or "") if branch.is_gst_registered else "",
                prices_include_gst=branch.prices_include_gst,
                platform_gstin=(fee_settings.platform_gstin if fee_settings and amounts["booking_fee_gst_amount"] > 0 else ""),
                cashback_amount=_money(token.cashback_amount),
                payment_status=token.payment_status,
                payment_status_display=token.get_payment_status_display(),
                created_by=created_by if (created_by and created_by.is_authenticated) else None,
                **amounts,
            )
            InvoiceItem.objects.bulk_create([
                InvoiceItem(
                    invoice=invoice,
                    description=description,
                    quantity=qty,
                    unit_price=_money(price),
                    amount=_money(price) * qty,
                )
                for description, qty, price in lines
            ])
            # Final number, e.g. INV-3-20261107-00042
            invoice.invoice_number = (
                f"INV-{branch.id}-{invoice.created_at:%Y%m%d}-{invoice.id:05d}"
            )
            invoice.save(update_fields=["invoice_number"])
    except IntegrityError:
        # Double click: another request already created it
        return Invoice.objects.get(token=token)
    return invoice


def send_invoice_email(invoice):
    """Email the invoice to the customer once. Never raises."""
    if invoice is None or invoice.email_sent or not invoice.customer_email:
        return False
    try:
        from django.urls import reverse
        from core.emails import build_email, from_address, site_link
        from reviews.services import rate_link
        from .views import invoice_link_key
        context = {
            "invoice": invoice,
            "items": invoice.items.all(),
            "rate_url": rate_link(invoice.token) if invoice.token_id else "",
            "invoice_url": site_link(reverse("billing:invoice_detail", args=[invoice.id]))
                           + f"?k={invoice_link_key(invoice)}",
            "preheader": f"Your invoice from {invoice.seller_name}. Total ₹{invoice.total_amount}",
        }
        text_body = render_to_string("billing/invoice_email.txt", context)
        html_body, _ = build_email(f"Invoice {invoice.invoice_number}", template="billing/invoice_email.html",
                                   text_body=text_body, **context)
        message = EmailMultiAlternatives(
            subject=f"Invoice {invoice.invoice_number} - {invoice.seller_name}",
            body=text_body,
            from_email=from_address(),
            to=[invoice.customer_email],
        )
        message.attach_alternative(html_body, "text/html")
        message.send()
    except Exception:
        logger.exception("Could not send invoice email for %s", invoice.invoice_number)
        return False
    Invoice.objects.filter(pk=invoice.pk).update(email_sent=True)
    invoice.email_sent = True
    return True
