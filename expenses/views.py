"""Expenses screen in the Business Workspace (branch admin / owner)."""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from workspace.views import _branch_or_deny

from .forms import ExpenseForm
from .models import Expense, ExpenseMonthTotal
from .services import delete_expense, save_expense


def _month_from(request):
    text = request.GET.get("month") or datetime.date.today().strftime("%Y-%m")
    try:
        datetime.datetime.strptime(text, "%Y-%m")
    except ValueError:
        text = datetime.date.today().strftime("%Y-%m")
    return text


@login_required
def expenses(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    month = _month_from(request)
    form = ExpenseForm(initial={"date": datetime.date.today()})
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.branch = branch
            expense.category = form.get_category()
            expense.created_by = request.user
            save_expense(expense)
            messages.success(request, f"Expense of ₹{expense.total_amount} saved ({expense.category}).")
            return redirect(f"{reverse('expenses:list', args=[branch.id])}?month={expense.month}")

    totals = ExpenseMonthTotal.objects.filter(branch=branch, month=month, count__gt=0).select_related("category")
    month_date = datetime.datetime.strptime(month, "%Y-%m").date()
    prev_month = (month_date.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    next_month = (month_date.replace(day=28) + datetime.timedelta(days=4)).strftime("%Y-%m")
    return render(request, "expenses/expenses.html", {
        "branch": branch, "active": "expenses", "form": form, "month": month, "month_date": month_date,
        "prev_month": prev_month,
        "next_month": next_month if next_month <= datetime.date.today().strftime("%Y-%m") else "",
        "expenses": Expense.objects.filter(branch=branch, month=month).select_related("category"),
        "totals": totals,
        "month_total": sum(t.total_amount for t in totals),
        "month_value": sum(t.expense_value for t in totals),
    })


@login_required
@require_POST
def expense_delete(request, branch_id, expense_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    expense = get_object_or_404(Expense, id=expense_id, branch=branch)
    month = expense.month
    delete_expense(expense)
    messages.success(request, "Expense deleted.")
    return redirect(f"{reverse('expenses:list', args=[branch.id])}?month={month}")
