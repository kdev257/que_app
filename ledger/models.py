"""
Chart of accounts and account-code mapping.
Nothing is posted yet: categories (services, item categories, expense categories) and system
items (GST, cash, bank, stock...) are LINKED to account codes now, so a ledger / Tally export
can be built later without changing the existing screens.
"""
from django.db import models

from .chart import SYSTEM_MAPPINGS

ACCOUNT_TYPES = [
    ("asset", "Asset"),
    ("liability", "Liability"),
    ("equity", "Capital / equity"),
    ("income", "Income"),
    ("expense", "Expense"),
]


class Account(models.Model):
    code = models.CharField(max_length=10, unique=True, help_text="e.g. 6001")
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    group = models.CharField(max_length=60, blank=True, help_text="Tally-style group, e.g. Indirect Expenses")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AccountMapping(models.Model):
    """Which account to use for system items (GST, payment modes, stock, discounts...)."""
    key = models.CharField(max_length=40, unique=True, choices=[(k, label) for k, label, _ in SYSTEM_MAPPINGS])
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="mappings")

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.get_key_display()} -> {self.account}"

    @classmethod
    def account_for(cls, key):
        row = cls.objects.select_related("account").filter(key=key).first()
        return row.account if row else None
