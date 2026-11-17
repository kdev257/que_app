"""Invoice creation and email. All amounts are calculated here once and stored."""
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from organization.gst import (
    RULE_GENERAL, TAX_INTER, TAX_NONE, code_for_name, financial_year, place_of_supply, split_tax, state_name,
)

from .models import CreditNote, DocumentSequence, Invoice, InvoiceItem

logger = logging.getLogger(__name__)
TWO_PLACES = Decimal("0.01")


def _money(value):
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _invoice_lines(token):
    """Return (source, [(description, qty, unit_price, sac_code), ...]) for a token."""
    category = token.branch.services_category if token.branch.services_category_id else None
    category_sac = token.branch.sac_code or (category.sac_code if category else "")  # branch choice first
    order = getattr(token, "restaurant_order", None) if hasattr(token, "restaurant_order") else None
    if order is not None:
        lines = [
            (item.menu_item.name.name, item.quantity, item.price, category_sac)
            for item in order.items.select_related("menu_item__name")
        ]
        return "restaurant", lines

    from queues.models import TokenService
    lines = [
        (str(ts.service.name), 1, ts.service.price, ts.service.sac_code or category_sac)
        for ts in TokenService.objects.filter(token=token).select_related("service__name")
    ]
    return "service", lines


def next_document_number(branch, doc_type, day):
    """Next consecutive number for this branch / document type / financial year.
    Invoice: DNS/26-27/00042 (max 16 characters). Credit note: DNSC/26-27/0001.
    Must be called inside transaction.atomic()."""
    fy = financial_year(day)
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
        branch=branch, doc_type=doc_type, financial_year=fy)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    prefix = branch.get_invoice_prefix()
    if doc_type == "credit_note":
        number = f"{prefix}C/{fy}/{seq.last_number:04d}"
    else:
        number = f"{prefix}/{fy}/{seq.last_number:05d}"
    return number, fy, seq.last_number


def _customer_details(token):
    """Return a dict: name, email, phone, gstin, business_name, state_code (state is '' if not known)."""
    details = {"name": "Walk-in Customer", "email": "", "phone": "", "gstin": "", "business_name": "", "state_code": ""}
    if token.user:
        user = token.user
        profile = getattr(user, "user_profile", None) if hasattr(user, "user_profile") else None
        details.update(name=f"{user.first_name} {user.last_name}".strip() or user.username, email=user.email or "")
        if profile:
            details.update(
                phone=profile.phone_no or "",
                gstin=(profile.gstin or "").strip().upper(),
                business_name=(profile.business_name or "").strip(),
                state_code=code_for_name(profile.state.name) if profile.state_id else "",
            )
    elif token.guest:
        details.update(name=token.guest.name, email=token.guest.email or "", phone=token.guest.phone_no or "")
    return details


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


def _platform_state(fee_settings):
    code = (getattr(fee_settings, "platform_state_code", "") or "").strip()
    gstin = (getattr(fee_settings, "platform_gstin", "") or "").strip()
    return code or (gstin[:2] if len(gstin) == 15 else "")


def calculate_amounts(subtotal, discount, booking_fee, branch, fee_settings=None, customer=None):
    """Pure calculation, returns a dict of all invoice amounts.
    fee_settings: the PlatformFee record (for GST on the booking fee), or None.
    customer: {'gstin': ..., 'state_code': ...} - decides the place of supply (general rule only).
    GST is charged on the amount after discount."""
    customer = customer or {}
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

    # Branch GST: CGST+SGST / CGST+UTGST / IGST by place of supply (IGST Act s.12)
    supplier = branch.gst_state_code or ""
    category = branch.services_category if branch.services_category_id else None
    rule = category.place_of_supply_rule if category else RULE_GENERAL
    pos = place_of_supply(rule, supplier, customer.get("gstin", ""), customer.get("state_code", "")) if (supplier and gst_rate > 0) else ""
    split = split_tax(gst, supplier, pos)

    # Booking fee GST is QuickQueue's own service: general rule, from the platform's state
    platform = _platform_state(fee_settings)
    fee_pos = place_of_supply(RULE_GENERAL, platform, customer.get("gstin", ""), customer.get("state_code", ""))
    fee_split = split_tax(fee_gst, platform, fee_pos)

    return {
        "subtotal": subtotal,
        "discount_amount": discount,
        "taxable_amount": taxable,
        "gst_percentage": gst_rate,
        "cgst_rate": _money(gst_rate / 2) if split["tax_type"] != TAX_INTER else Decimal("0.00"),
        "sgst_rate": _money(gst_rate / 2) if split["tax_type"] != TAX_INTER else Decimal("0.00"),
        "igst_rate": gst_rate if split["tax_type"] == TAX_INTER else Decimal("0.00"),
        "cgst_amount": split["cgst"],
        "sgst_amount": split["sgst"],
        "utgst_amount": split["utgst"],
        "igst_amount": split["igst"],
        "gst_amount": gst,
        "tax_type": split["tax_type"] if gst_rate > 0 else TAX_NONE,
        "supplier_state_code": supplier,
        "place_of_supply_code": pos,
        "place_of_supply_name": state_name(pos),
        "booking_fee": fee_taxable,
        "booking_fee_gst_percentage": fee_rate,
        "booking_fee_gst_amount": fee_gst,
        "booking_fee_tax_type": fee_split["tax_type"] if fee_gst > 0 else TAX_NONE,
        "booking_fee_cgst": fee_split["cgst"],
        "booking_fee_sgst": fee_split["sgst"] + fee_split["utgst"],
        "booking_fee_igst": fee_split["igst"],
        "total_amount": taxable + gst + fee_taxable + fee_gst,
    }


def create_invoice_for_token(token, created_by=None):
    """Create (once) and return the invoice for a completed token."""
    existing = Invoice.objects.filter(token=token).first()
    if existing:
        return existing

    branch = token.branch
    source, lines = _invoice_lines(token)
    subtotal = sum((_money(price) * qty for _, qty, price, _ in lines), Decimal("0.00"))
    fee_settings = active_platform_fee()
    customer = _customer_details(token)
    amounts = calculate_amounts(subtotal, token.discount_amount, token.booking_fee, branch, fee_settings, customer)

    try:
        with transaction.atomic():
            today = datetime.date.today()
            number, fy, serial = next_document_number(branch, "invoice", today)
            invoice = Invoice.objects.create(
                invoice_number=number,
                financial_year=fy,
                serial_number=serial,
                payment_mode="online" if token.razorpay_payment_id else "",
                token=token,
                branch=branch,
                source=source,
                token_number=token.token_number,
                service_date=token.token_date,
                seller_name=f"{branch.name} - {branch.organization.name}",
                seller_address=_seller_address(branch),
                seller_phone=branch.phone or "",
                seller_email=branch.email or "",
                customer_name=customer["name"],
                customer_email=customer["email"],
                customer_phone=customer["phone"],
                customer_gstin=customer["gstin"] if branch.is_gst_registered else "",
                customer_business_name=customer["business_name"] if (branch.is_gst_registered and customer["gstin"]) else "",
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
                    sac_code=sac,
                    quantity=qty,
                    unit_price=_money(price),
                    amount=_money(price) * qty,
                )
                for description, qty, price, sac in lines
            ])
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


def create_credit_note(invoice, amount, reason, note="", created_by=None):
    """Make a credit note for part or all of the branch's part of an invoice (amount includes GST).
    Taxable value and GST are split in the same ratio as the invoice, and stored."""
    from django.db.models import F
    amount = _money(amount)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if amount <= 0 or amount > invoice.can_credit_amount:
            raise ValueError(f"Amount must be between 0.01 and {invoice.can_credit_amount}.")
        branch_total = invoice.branch_amount
        taxable = _money(invoice.taxable_amount * amount / branch_total) if branch_total else amount
        gst = amount - taxable
        split = split_tax(gst, invoice.supplier_state_code, invoice.place_of_supply_code or invoice.supplier_state_code)
        if invoice.tax_type in ("", TAX_NONE):
            split["tax_type"] = TAX_NONE if gst == 0 else split["tax_type"]
        number, fy, serial = next_document_number(invoice.branch, "credit_note", datetime.date.today())
        credit_note = CreditNote.objects.create(
            invoice=invoice, branch=invoice.branch, number=number, financial_year=fy, serial_number=serial,
            reason=reason, note=note[:255], tax_type=invoice.tax_type or split["tax_type"],
            taxable_amount=taxable, gst_amount=gst, total_amount=amount,
            cgst_amount=split["cgst"], sgst_amount=split["sgst"], utgst_amount=split["utgst"], igst_amount=split["igst"],
            created_by=created_by if (created_by and created_by.is_authenticated) else None,
        )
        Invoice.objects.filter(pk=invoice.pk).update(credited_amount=F("credited_amount") + amount)
    return credit_note
