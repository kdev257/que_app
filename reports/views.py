"""Profit & loss screen (branch admin / owner)."""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from organization.models import Branch
from organization.permissions import is_org_owner
from workspace.views import _branch_or_deny

from .models import ProfitLossReport
from .services import generate_profit_loss


def _presets(today):
    first = today.replace(day=1)
    last_month_end = first - datetime.timedelta(days=1)
    fy_start = datetime.date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    last_fy_start = fy_start.replace(year=fy_start.year - 1)
    return [
        ("This month", first, today),
        ("Last month", last_month_end.replace(day=1), last_month_end),
        ("This financial year", fy_start, today),
        ("Last financial year", last_fy_start, fy_start - datetime.timedelta(days=1)),
    ]


def _can_see_all(user, branch):
    return user.is_superuser or is_org_owner(user, branch.organization_id)


@login_required
def profit_loss(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    today = datetime.date.today()
    can_all = _can_see_all(request.user, branch)
    reports = ProfitLossReport.objects.filter(Q(branch=branch) | Q(branch__isnull=True, organization=branch.organization)
                                              if can_all else Q(branch=branch)).select_related("branch")[:30]
    return render(request, "reports/profit_loss.html", {
        "branch": branch, "active": "reports", "presets": _presets(today), "today": today,
        "default_from": today.replace(day=1), "can_all": can_all, "reports": reports,
    })


@login_required
@require_POST
def profit_loss_generate(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    try:
        period_from = datetime.date.fromisoformat(request.POST.get("period_from", ""))
        period_to = datetime.date.fromisoformat(request.POST.get("period_to", ""))
    except ValueError:
        messages.error(request, "Please choose both dates.")
        return redirect("reports:profit_loss", branch_id=branch.id)
    if period_from > period_to:
        messages.error(request, "'From' date must be before the 'To' date.")
        return redirect("reports:profit_loss", branch_id=branch.id)
    if period_to > datetime.date.today():
        messages.error(request, "'To' date cannot be in the future.")
        return redirect("reports:profit_loss", branch_id=branch.id)
    if request.POST.get("scope") == "all" and _can_see_all(request.user, branch):
        branches = list(Branch.objects.filter(organization=branch.organization))
        report = generate_profit_loss(branch.organization, branches, period_from, period_to, None, request.user)
    else:
        report = generate_profit_loss(branch.organization, [branch], period_from, period_to, branch, request.user)
    return redirect("reports:profit_loss_detail", branch_id=branch.id, report_id=report.id)


@login_required
def profit_loss_detail(request, branch_id, report_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    report = get_object_or_404(ProfitLossReport.objects.select_related("branch", "organization"), id=report_id)
    allowed = report.branch_id == branch.id or (
        report.branch_id is None and report.organization_id == branch.organization_id and _can_see_all(request.user, branch))
    if not allowed:
        messages.error(request, "You cannot view this report.")
        return redirect("reports:profit_loss", branch_id=branch.id)
    return render(request, "reports/profit_loss_detail.html", {
        "branch": branch, "active": "reports", "report": report, "lines": report.lines.all(),
    })
