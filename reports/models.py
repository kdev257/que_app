"""
Profit & loss for a period. When the owner clicks "Generate", all figures are worked out once
from invoices, credit notes, stock and expenses, and STORED here. The report page only reads them.
"""
from django.conf import settings
from django.db import models


class ProfitLossReport(models.Model):
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="pl_reports")
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="pl_reports", help_text="Empty = all branches of the business")
    period_from = models.DateField()
    period_to = models.DateField()
    # Income
    sales = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Taxable value of invoices (without GST)")
    credit_notes = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    invoice_count = models.PositiveIntegerField(default=0)
    # Cost of items used
    opening_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    purchases = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_of_items_used = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Expenses and result
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_stock_counted = models.BooleanField(default=False, help_text="A closing stock count exists for the last day")
    warnings = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = self.branch.name if self.branch_id else f"{self.organization.name} (all branches)"
        return f"P&L {scope} {self.period_from} to {self.period_to}"

    @property
    def is_loss(self):
        return self.net_profit < 0

    @property
    def warning_list(self):
        return [w for w in self.warnings.split("\n") if w.strip()]


class ProfitLossLine(models.Model):
    """Expense lines (one per expense category) with their account code."""
    report = models.ForeignKey(ProfitLossReport, on_delete=models.CASCADE, related_name="lines")
    label = models.CharField(max_length=120)
    account_code = models.CharField(max_length=10, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort", "label"]

    def __str__(self):
        return f"{self.label}: {self.amount}"
