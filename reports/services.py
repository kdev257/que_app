"""Work out a profit & loss statement once and store it."""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum

from billing.models import CreditNote, Invoice
from expenses.models import Expense
from inventory.models import Receipt, StockCount, StockMove

from .models import ProfitLossLine, ProfitLossReport

ZERO = Decimal("0.00")


def _sum(qs, field):
    return qs.aggregate(total=Sum(field))["total"] or ZERO


def stock_value_as_at(branches, day):
    """Value of stock (at cost) as per the stock ledger at the end of a day."""
    return _sum(StockMove.objects.filter(branch__in=branches, date__lte=day), "value")


def generate_profit_loss(organization, branches, period_from, period_to, single_branch=None, user=None):
    """branches: list/queryset of branches included. Returns the stored report."""
    warnings = []
    invoices = Invoice.objects.filter(branch__in=branches, created_at__date__gte=period_from,
                                      created_at__date__lte=period_to)
    sales = _sum(invoices, "taxable_amount")
    invoice_count = invoices.count()
    credit = _sum(CreditNote.objects.filter(branch__in=branches, created_at__date__gte=period_from,
                                            created_at__date__lte=period_to), "taxable_amount")

    opening = stock_value_as_at(branches, period_from - datetime.timedelta(days=1))
    purchases = _sum(Receipt.objects.filter(branch__in=branches, bill_date__gte=period_from,
                                            bill_date__lte=period_to), "stock_value")
    closing = stock_value_as_at(branches, period_to)
    counted = all(StockCount.objects.filter(branch=b, status="approved", as_at=period_to).exists() for b in branches)
    if purchases and not counted:
        warnings.append(f"No approved closing stock count on {period_to:%d %b %Y}. Closing stock is taken from the "
                        "books, so the cost of items used may be too low. Count stock on the last day for an accurate profit.")
    if StockCount.objects.filter(branch__in=branches, status="pending").exists():
        warnings.append("A staff stock count is waiting for approval.")

    expense_rows = (Expense.objects.filter(branch__in=branches, date__gte=period_from, date__lte=period_to)
                    .values("category__name", "category__account__code")
                    .annotate(total=Sum("expense_value"), n=Count("id")).order_by("category__account__code", "category__name"))

    net_sales = sales - credit
    cost_used = opening + purchases - closing
    gross = net_sales - cost_used
    total_exp = sum((r["total"] or ZERO for r in expense_rows), ZERO)

    with transaction.atomic():
        report = ProfitLossReport.objects.create(
            organization=organization, branch=single_branch, period_from=period_from, period_to=period_to,
            sales=sales, credit_notes=credit, net_sales=net_sales, invoice_count=invoice_count,
            opening_stock=opening, purchases=purchases, closing_stock=closing, cost_of_items_used=cost_used,
            gross_profit=gross, total_expenses=total_exp, net_profit=gross - total_exp,
            closing_stock_counted=counted, warnings="\n".join(warnings), created_by=user,
        )
        ProfitLossLine.objects.bulk_create([
            ProfitLossLine(report=report, label=r["category__name"], account_code=r["category__account__code"] or "",
                           amount=r["total"] or ZERO, sort=i)
            for i, r in enumerate(expense_rows)
        ])
    return report
