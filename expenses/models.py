"""
Expenses (rent, salary, electricity ...) for simple books.
Amounts, GST and monthly totals are worked out once when an expense is saved and STORED,
so profit & loss and the expense page read them without calculating on page load.
"""
import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

DEFAULT_EXPENSE_CATEGORIES = [
    "Rent", "Salaries & wages", "Electricity", "Water", "Internet & phone", "Repairs & maintenance",
    "Marketing & ads", "Bank & payment charges", "Professional fees (CA, legal)", "Licences & fees",
    "Travel & conveyance", "Staff food & welfare", "Laundry", "Commission paid", "Software & subscriptions",
    "Insurance", "Other",
]
PAYMENT_MODES = [("cash", "Cash"), ("upi", "UPI"), ("card", "Card"), ("bank", "Bank transfer"), ("other", "Other")]


class ExpenseCategory(models.Model):
    """Common list of expense categories (pick one, or add a new one from the form)."""
    name = models.CharField(max_length=80, unique=True)
    # Account code for future accounting (e.g. 6001 Rent); new categories go to 6999 Other expenses
    account = models.ForeignKey("ledger.Account", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="expense_categories", verbose_name="Account code")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Expense categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.account_id is None:  # link new categories to a default account code
            from ledger.models import Account
            self.account = Account.objects.filter(code="6999").first()
        super().save(*args, **kwargs)


class Expense(models.Model):
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="expenses")
    date = models.DateField(default=datetime.date.today)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    description = models.CharField(max_length=200, blank=True, help_text="e.g. November rent")
    paid_to = models.CharField(max_length=150, blank=True, help_text="e.g. landlord, electricity board")
    paid_to_gstin = models.CharField(max_length=15, blank=True, verbose_name="Paid to GSTIN")
    amount_entered = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount as on the bill")
    amount_includes_gst = models.BooleanField(default=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODES, default="cash")
    bill_file = models.FileField(upload_to="expense_bills/", blank=True)
    # Stored results
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    itc_claimable = models.BooleanField(default=False)
    expense_value = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        help_text="Cost for profit & loss (GST included when it cannot be claimed)")
    month = models.CharField(max_length=7, db_index=True, help_text="YYYY-MM")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.category} {self.total_amount} on {self.date}"


class ExpenseMonthTotal(models.Model):
    """Stored total per branch, month and category (kept up to date on every add/delete)."""
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="expense_totals")
    month = models.CharField(max_length=7, help_text="YYYY-MM")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name="month_totals")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_claimable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("branch", "month", "category")
        ordering = ["month", "category__name"]

    def __str__(self):
        return f"{self.branch} {self.month} {self.category}: {self.expense_value}"
