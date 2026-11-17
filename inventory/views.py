"""Workspace screens: stock, items, suppliers, purchase receipts (branch admin / owner)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.views import _branch_or_deny

from .forms import DIRECTORY_FIELDS, ItemForm, ReceiptForm, ReceiptLineFormSet, SupplierForm
from .models import Item, Receipt, StockBalance, StockCount, Supplier, business_type_of
from .services import approve_count, book_quantities, post_receipt, post_stock_count, submit_staff_count


@login_required
def stock(request, branch_id):
    """Stock of this branch + add item."""
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    org = branch.organization
    kind = business_type_of(branch)
    form = ItemForm(organization=org, business_type=kind)
    if request.method == "POST":
        form = ItemForm(request.POST, organization=org, business_type=kind)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = org
            item.save()
            messages.success(request, f"Item '{item.name}' added.")
            return redirect("inventory:stock", branch_id=branch.id)
    from .models import ItemName
    name_defaults = {str(n.id): {"unit": n.unit, "category": n.category}
                     for n in ItemName.objects.filter(business_type__in=form.allowed_types)}
    balances = {b.item_id: b for b in StockBalance.objects.filter(branch=branch)}
    items = list(Item.objects.filter(organization=org).order_by("-is_active", "category", "name"))
    for item in items:
        item.balance = balances.get(item.id)
    totals = StockBalance.objects.filter(branch=branch).aggregate(value=Sum("value"))
    return render(request, "inventory/stock.html", {
        "branch": branch, "active": "stock", "form": form, "items": items, "name_defaults": name_defaults,
        "stock_value": totals["value"] or 0,
        "low_count": sum(1 for b in balances.values() if b.is_low),
    })


@login_required
def item_edit(request, branch_id, item_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    item = get_object_or_404(Item, id=item_id, organization=branch.organization)
    form = ItemForm(request.POST or None, instance=item, organization=branch.organization,
                    business_type=business_type_of(branch))
    if request.method == "POST":
        if request.POST.get("toggle"):
            item.is_active = not item.is_active
            item.save(update_fields=["is_active"])
            messages.success(request, "Item switched on." if item.is_active else "Item switched off.")
            return redirect("inventory:stock", branch_id=branch.id)
        if form.is_valid():
            form.save()
            for bal in StockBalance.objects.filter(item=item):
                bal.is_low = bal.quantity < item.min_stock
                bal.save(update_fields=["is_low"])
            messages.success(request, "Item saved.")
            return redirect("inventory:stock", branch_id=branch.id)
    return render(request, "workspace/form_page.html", {
        "form": form, "title": f"Edit item: {item.name}", "branch": branch, "active": "stock",
    })


@login_required
def suppliers(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    org = branch.organization
    kind = business_type_of(branch)
    form = SupplierForm(organization=org, business_type=kind, city=branch.city or "")
    if request.method == "POST":
        form = SupplierForm(request.POST, organization=org, business_type=kind, city=branch.city or "")
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = org
            supplier.save()
            messages.success(request, f"Supplier '{supplier.name}' added.")
            return redirect("inventory:suppliers", branch_id=branch.id)
    return render(request, "inventory/suppliers.html", {
        "branch": branch, "active": "stock", "form": form,
        "suppliers": Supplier.objects.filter(organization=org).order_by("-is_active", "name"),
        # details of the shared suppliers, to fill the form when one is picked
        "directory_details": {str(d.id): {f: getattr(d, f) for f in DIRECTORY_FIELDS} for d in form.directory_choices},
    })


@login_required
def supplier_edit(request, branch_id, supplier_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    supplier = get_object_or_404(Supplier, id=supplier_id, organization=branch.organization)
    form = SupplierForm(request.POST or None, instance=supplier, organization=branch.organization)
    if request.method == "POST":
        if request.POST.get("toggle"):
            supplier.is_active = not supplier.is_active
            supplier.save(update_fields=["is_active"])
            return redirect("inventory:suppliers", branch_id=branch.id)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier saved.")
            return redirect("inventory:suppliers", branch_id=branch.id)
    return render(request, "workspace/form_page.html", {
        "form": form, "title": f"Edit supplier: {supplier.name}", "branch": branch, "active": "stock",
    })


@login_required
def receipts(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    rows = Receipt.objects.filter(branch=branch).select_related("supplier")[:200]
    return render(request, "inventory/receipts.html", {"branch": branch, "active": "stock", "receipts": rows})


@login_required
def receipt_new(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    org = branch.organization
    if not Supplier.objects.filter(organization=org, is_active=True).exists() or \
            not Item.objects.filter(organization=org, is_active=True).exists():
        messages.info(request, "First add at least one supplier and one item.")
        return redirect("inventory:suppliers" if not Supplier.objects.filter(organization=org).exists()
                        else "inventory:stock", branch_id=branch.id)
    form = ReceiptForm(branch=branch)
    formset = ReceiptLineFormSet(prefix="lines", form_kwargs={"organization": org})
    if request.method == "POST":
        form = ReceiptForm(request.POST, request.FILES, branch=branch)
        formset = ReceiptLineFormSet(request.POST, prefix="lines", form_kwargs={"organization": org})
        if form.is_valid() and formset.is_valid():
            lines = [f.cleaned_data for f in formset if f.cleaned_data.get("item")]
            if not lines:
                messages.error(request, "Add at least one item line.")
            else:
                receipt = form.save(commit=False)
                receipt.branch = branch
                receipt.created_by = request.user
                post_receipt(receipt, lines, request.user)
                messages.success(request, f"Purchase bill saved. Stock increased by ₹{receipt.stock_value}.")
                return redirect("inventory:receipt_detail", branch_id=branch.id, receipt_id=receipt.id)
    return render(request, "inventory/receipt_form.html", {
        "branch": branch, "active": "stock", "form": form, "formset": formset,
    })


@login_required
def receipt_detail(request, branch_id, receipt_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    receipt = get_object_or_404(Receipt.objects.select_related("supplier"), id=receipt_id, branch=branch)
    return render(request, "inventory/receipt_detail.html", {
        "branch": branch, "active": "stock", "receipt": receipt, "lines": receipt.lines.select_related("item"),
    })


# ---------------------------------------------------------------------------
# Closing stock (count "as at" a date). Items used = book stock - counted stock.
# ---------------------------------------------------------------------------
@login_required
def stock_counts(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    return render(request, "inventory/stock_counts.html", {
        "branch": branch, "active": "stock",
        "counts": StockCount.objects.filter(branch=branch).select_related("counted_by", "approved_by")[:60],
        "pending": StockCount.objects.filter(branch=branch, status="pending").first(),
    })


@login_required
def stock_count_new(request, branch_id):
    import datetime
    from decimal import Decimal, InvalidOperation
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    today = datetime.date.today()
    raw_date = request.POST.get("as_at") or request.GET.get("as_at") or today.isoformat()
    try:
        as_at = datetime.date.fromisoformat(raw_date)
    except ValueError:
        as_at = today
    last = StockCount.objects.filter(branch=branch, status="approved").order_by("-as_at").first()
    error = _count_date_error(branch, as_at, today, last)

    balances = set(StockBalance.objects.filter(branch=branch).values_list("item_id", flat=True))
    items = [i for i in Item.objects.filter(organization=branch.organization).order_by("category", "name")
             if i.is_active or i.id in balances]
    book = book_quantities(branch, as_at)
    rows = [{"item": i, "book": book.get(i.id, Decimal("0")), "value": request.POST.get(f"count_{i.id}", "")}
            for i in items]

    if request.method == "POST" and not error:
        counted, bad = {}, []
        for row in rows:
            text = (row["value"] or "").strip()
            try:
                qty = Decimal(text) if text != "" else row["book"]
                if qty < 0:
                    raise InvalidOperation
                counted[row["item"]] = qty
            except (InvalidOperation, ValueError):
                bad.append(row["item"].name)
        if bad:
            error = "Please enter a valid quantity (0 or more) for: " + ", ".join(bad[:5])
        elif not counted:
            error = "There are no items to count yet. Add items and enter a purchase bill first."
        else:
            count = StockCount(branch=branch, as_at=as_at, notes=request.POST.get("notes", "")[:255],
                               created_by=request.user)
            post_stock_count(count, counted, request.user)
            messages.success(request, f"Closing stock as at {as_at:%d %b %Y} saved: \u20b9{count.closing_value}. "
                                      f"Items used: \u20b9{count.used_value}.")
            return redirect("inventory:stock_count_detail", branch_id=branch.id, count_id=count.id)

    return render(request, "inventory/stock_count_form.html", {
        "branch": branch, "active": "stock", "rows": rows, "as_at": as_at, "today": today,
        "last": last, "error": error,
    })


@login_required
def stock_count_detail(request, branch_id, count_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    count = get_object_or_404(StockCount, id=count_id, branch=branch)
    if count.status != "approved":
        return redirect("inventory:stock_count_review", branch_id=branch.id, count_id=count.id)
    return render(request, "inventory/stock_count_detail.html", {
        "branch": branch, "active": "stock", "count": count, "lines": count.lines.select_related("item"),
    })


def _count_date_error(branch, as_at, today, last, exclude_id=None):
    if as_at > today:
        return "The date cannot be in the future."
    if last and as_at <= last.as_at:
        return f"Closing stock is already entered up to {last.as_at:%d %b %Y}. Choose a later date."
    other = StockCount.objects.filter(branch=branch, as_at=as_at).exclude(id=exclude_id).first()
    if other:
        return f"A stock count for {as_at:%d %b %Y} already exists ({other.get_status_display().lower()})."
    return ""


def _count_items(branch):
    balances = set(StockBalance.objects.filter(branch=branch).values_list("item_id", flat=True))
    return [i for i in Item.objects.filter(organization=branch.organization).order_by("category", "name")
            if i.is_active or i.id in balances]


@login_required
def staff_stock_count(request, branch_id):
    """Staff screen: enter counted quantities only (no prices or values) and submit for approval."""
    import datetime
    from decimal import Decimal, InvalidOperation
    from organization.models import Branch
    from organization.permissions import SALON_STAFF_ROLES, can_manage_branch, deny
    branch = get_object_or_404(Branch, id=branch_id)
    if not can_manage_branch(request.user, branch.id, SALON_STAFF_ROLES):
        return deny(request)
    pending = StockCount.objects.filter(branch=branch, status="pending").first()
    returned = StockCount.objects.filter(branch=branch, status="returned").first()
    today = datetime.date.today()
    last = StockCount.objects.filter(branch=branch, status="approved").order_by("-as_at").first()
    items = _count_items(branch)
    previous = {l.item_id: l.counted_qty for l in returned.lines.all()} if returned else {}
    as_at = returned.as_at if returned else today
    error = ""

    if request.method == "POST" and not pending:
        try:
            as_at = datetime.date.fromisoformat(request.POST.get("as_at", ""))
        except ValueError:
            as_at = today
        error = _count_date_error(branch, as_at, today, last, exclude_id=returned.id if returned else None)
        counted, bad = {}, []
        for item in items:
            text = (request.POST.get(f"count_{item.id}") or "").strip()
            previous[item.id] = text
            if text == "":
                counted[item] = None
                continue
            try:
                qty = Decimal(text)
                if qty < 0:
                    raise InvalidOperation
                counted[item] = qty
            except (InvalidOperation, ValueError):
                bad.append(item.name)
        if not error and bad:
            error = "Please enter a valid quantity (0 or more) for: " + ", ".join(bad[:5])
        if not error and not any(v is not None for v in counted.values()):
            error = "Enter the counted quantity of at least one item."
        if not error:
            submit_staff_count(branch, as_at, counted, request.user, count=returned)
            messages.success(request, "Stock count sent to the branch admin for approval. Thank you!")
            return redirect("inventory:staff_stock_count", branch_id=branch.id)

    rows = [{"item": i, "value": previous.get(i.id, "")} for i in items]
    from organization.permissions import home_url_for
    back_url = home_url_for(request.user)
    if back_url == reverse("index"):
        back_url = reverse("inventory:stock_counts", args=[branch.id])
    return render(request, "inventory/staff_stock_count.html", {
        "branch": branch, "rows": rows, "back_url": back_url, "as_at": as_at, "today": today, "pending": pending,
        "returned": returned, "error": error, "last": last,
    })


@login_required
def stock_count_review(request, branch_id, count_id):
    """Branch admin: check a staff count (book vs counted), correct it, then approve or send back."""
    import datetime
    from decimal import Decimal, InvalidOperation
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    count = get_object_or_404(StockCount, id=count_id, branch=branch)
    if count.status == "approved":
        return redirect("inventory:stock_count_detail", branch_id=branch.id, count_id=count.id)
    staff_qty = {l.item_id: l.counted_qty for l in count.lines.all()}
    items = _count_items(branch)
    book = book_quantities(branch, count.as_at)
    rows = []
    for item in items:
        bal = StockBalance.objects.filter(branch=branch, item=item).first()
        counted = staff_qty.get(item.id)
        rows.append({"item": item, "book": book.get(item.id, Decimal("0")), "staff": counted,
                     "value": request.POST.get(f"count_{item.id}",
                                               counted if counted is not None else book.get(item.id, Decimal("0"))),
                     "avg_cost": bal.avg_cost if bal else Decimal("0")})
    error = ""
    if request.method == "POST":
        if request.POST.get("action") == "return":
            note = request.POST.get("return_note", "").strip()
            if not note:
                error = "Please write why you are sending it back."
            else:
                count.status, count.return_note = "returned", note[:255]
                count.save(update_fields=["status", "return_note"])
                messages.success(request, "Stock count sent back to staff.")
                return redirect("inventory:stock_counts", branch_id=branch.id)
        else:
            last = StockCount.objects.filter(branch=branch, status="approved").order_by("-as_at").first()
            error = _count_date_error(branch, count.as_at, datetime.date.today(), last, exclude_id=count.id)
            counted, bad = {}, []
            for row in rows:
                try:
                    qty = Decimal(str(row["value"]).strip())
                    if qty < 0:
                        raise InvalidOperation
                    counted[row["item"]] = qty
                except (InvalidOperation, ValueError):
                    bad.append(row["item"].name)
            if not error and bad:
                error = "Please enter a valid quantity (0 or more) for: " + ", ".join(bad[:5])
            if not error:
                approve_count(count, counted, request.user)
                messages.success(request, f"Closing stock as at {count.as_at:%d %b %Y} approved: \u20b9{count.closing_value}.")
                return redirect("inventory:stock_count_detail", branch_id=branch.id, count_id=count.id)
    return render(request, "inventory/stock_count_review.html", {
        "branch": branch, "active": "stock", "count": count, "rows": rows, "error": error,
    })
