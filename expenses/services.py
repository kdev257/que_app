"""Save / delete an expense: work out GST once, store it, and keep the monthly totals current."""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F

from .models import Expense, ExpenseMonthTotal

TWO = Decimal("0.01")


def _money(value):
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def work_out(expense):
    """Fill taxable / GST / total / ITC / P&L value on the expense (not saved)."""
    amount, rate = _money(expense.amount_entered), Decimal(expense.gst_rate or 0)
    if rate > 0 and expense.amount_includes_gst:
        taxable = _money(amount * 100 / (100 + rate))
        gst = amount - taxable
    else:
        taxable = amount
        gst = _money(amount * rate / 100)
    branch = expense.branch
    itc = bool(gst > 0 and branch.itc_allowed and branch.is_gst_registered and expense.paid_to_gstin)
    expense.taxable_amount, expense.gst_amount, expense.total_amount = taxable, gst, taxable + gst
    expense.itc_claimable = itc
    expense.expense_value = taxable if itc else taxable + gst
    expense.month = expense.date.strftime("%Y-%m")
    return expense


def _bump(expense, sign):
    total, _ = ExpenseMonthTotal.objects.select_for_update().get_or_create(
        branch=expense.branch, month=expense.month, category=expense.category)
    ExpenseMonthTotal.objects.filter(pk=total.pk).update(
        total_amount=F("total_amount") + sign * expense.total_amount,
        gst_claimable=F("gst_claimable") + sign * (expense.gst_amount if expense.itc_claimable else 0),
        expense_value=F("expense_value") + sign * expense.expense_value,
        count=F("count") + sign,
    )


def save_expense(expense):
    with transaction.atomic():
        work_out(expense)
        expense.save()
        _bump(expense, 1)
    return expense


def delete_expense(expense):
    with transaction.atomic():
        _bump(expense, -1)
        if expense.bill_file:
            expense.bill_file.delete(save=False)
        expense.delete()
