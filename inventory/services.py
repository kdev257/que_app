"""Stock postings. Amounts are calculated once here and stored."""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from .models import ReceiptLine, StockBalance, StockMove

TWO = Decimal("0.01")
FOUR = Decimal("0.0001")


def money(value):
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def line_amounts(quantity, rate, gst_rate, rates_include_gst, itc_allowed):
    """Return (taxable, gst, total, stock_value) for one bill line.
    Stock value = taxable if input tax credit can be claimed, else taxable + GST (GST becomes cost)."""
    gross = money(Decimal(quantity) * Decimal(rate))
    gst_rate = Decimal(gst_rate or 0)
    if rates_include_gst and gst_rate > 0:
        taxable = money(gross * 100 / (100 + gst_rate))
        gst = gross - taxable
    else:
        taxable = gross
        gst = money(taxable * gst_rate / 100)
    total = taxable + gst
    return taxable, gst, total, (taxable if itc_allowed else total)


def _apply_move(branch, item, quantity, value):
    """Add a stock move to the stored balance (weighted average cost)."""
    bal, _ = StockBalance.objects.select_for_update().get_or_create(branch=branch, item=item)
    bal.quantity += quantity
    bal.value = money(bal.value + value)
    if bal.quantity <= 0:
        bal.value = Decimal("0.00") if bal.quantity == 0 else bal.value
    bal.avg_cost = (bal.value / bal.quantity).quantize(FOUR) if bal.quantity > 0 else bal.avg_cost
    bal.is_low = bal.quantity < item.min_stock
    bal.save()
    return bal


def post_receipt(receipt, lines, user=None):
    """lines: list of dicts {item, quantity, rate, gst_rate}. Saves lines, totals, stock moves and balances."""
    itc = receipt.branch.itc_allowed and receipt.branch.is_gst_registered and bool(receipt.supplier.gstin)
    with transaction.atomic():
        receipt.itc_claimable = itc
        receipt.supplier_gstin = receipt.supplier.gstin
        receipt.save()
        totals = [Decimal("0.00")] * 4
        for data in lines:
            taxable, gst, total, value = line_amounts(data["quantity"], data["rate"], data["gst_rate"],
                                                      receipt.rates_include_gst, itc)
            line = ReceiptLine.objects.create(receipt=receipt, item=data["item"], quantity=data["quantity"],
                                              rate=data["rate"], gst_rate=data["gst_rate"], taxable_amount=taxable,
                                              gst_amount=gst, total_amount=total, stock_value=value)
            StockMove.objects.create(branch=receipt.branch, item=data["item"], date=receipt.bill_date, kind="receipt",
                                     quantity=data["quantity"], value=value, receipt_line=line,
                                     note=f"{receipt.supplier.name} bill {receipt.bill_number}", created_by=user)
            _apply_move(receipt.branch, data["item"], Decimal(data["quantity"]), value)
            totals = [a + b for a, b in zip(totals, (taxable, gst, total, value))]
        receipt.taxable_amount, receipt.gst_amount, receipt.total_amount, receipt.stock_value = totals
        receipt.save(update_fields=["taxable_amount", "gst_amount", "total_amount", "stock_value",
                                    "itc_claimable", "supplier_gstin"])
    return receipt


def book_quantities(branch, as_at):
    """Quantity of each item as per the stock ledger up to and including a date: {item_id: qty}."""
    from django.db.models import Sum
    rows = (StockMove.objects.filter(branch=branch, date__lte=as_at)
            .values("item_id").annotate(qty=Sum("quantity")))
    return {r["item_id"]: r["qty"] or Decimal("0") for r in rows}


def post_stock_count(count, counted, user=None):
    """counted: {item: counted_qty}. Saves lines, one 'issue' move per item for what was used
    (or an 'adjust' move if more was found), and updates the stored balances."""
    from .models import StockCountLine
    with transaction.atomic():
        count.save()
        book = book_quantities(count.branch, count.as_at)
        closing_total, used_total = Decimal("0.00"), Decimal("0.00")
        for item, qty in counted.items():
            qty = Decimal(qty)
            bal = StockBalance.objects.select_for_update().filter(branch=count.branch, item=item).first()
            avg = bal.avg_cost if bal else Decimal("0")
            book_qty = Decimal(book.get(item.id, 0))
            used = book_qty - qty
            used_value = money(used * avg)
            closing_value = money(qty * avg)
            StockCountLine.objects.create(count=count, item=item, book_qty=book_qty, counted_qty=qty, used_qty=used,
                                          avg_cost=avg, closing_value=closing_value, used_value=used_value)
            if used != 0:
                StockMove.objects.create(branch=count.branch, item=item, date=count.as_at,
                                         kind="issue" if used > 0 else "adjust", quantity=-used, value=-used_value,
                                         note=f"Closing stock as at {count.as_at:%d %b %Y}", created_by=user)
                _apply_move(count.branch, item, -used, -used_value)
            closing_total += closing_value
            used_total += used_value
        count.closing_value, count.used_value = closing_total, used_total
        count.save(update_fields=["closing_value", "used_value"])
    return count


def submit_staff_count(branch, as_at, counted, user, count=None):
    """Staff count: save quantities only (no values) and mark it 'pending' for the branch admin.
    counted: {item: qty or None (not counted)}."""
    from .models import StockCount, StockCountLine
    with transaction.atomic():
        if count is None:
            count = StockCount(branch=branch)
        count.as_at, count.status, count.counted_by, count.return_note = as_at, "pending", user, ""
        count.created_by = count.created_by or user
        count.save()
        count.lines.all().delete()
        StockCountLine.objects.bulk_create([
            StockCountLine(count=count, item=item, counted_qty=qty) for item, qty in counted.items()
        ])
    return count


def approve_count(count, counted, user):
    """Branch admin approves a staff count (with any corrections): post it like a normal closing stock."""
    from django.utils import timezone
    with transaction.atomic():
        count.lines.all().delete()
        count.status, count.approved_by, count.approved_at = "approved", user, timezone.now()
        post_stock_count(count, counted, user)
    return count
