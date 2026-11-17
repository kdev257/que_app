"""
Stock & purchases (simple books).
- Items and suppliers belong to the organization (shared by its branches).
- Stock is kept per branch. Every receipt / issue is a StockMove, and the running
  quantity, value and average cost are STORED in StockBalance (weighted average cost),
  so profit & loss can read the closing stock value without calculating on page load.
- Branches without input tax credit (5% salon/restaurant): GST paid is part of the cost.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

UNIT_CHOICES = [
    ("pcs", "Pieces"), ("ml", "ml"), ("l", "Litre"), ("g", "Gram"), ("kg", "Kg"),
    ("box", "Box"), ("pack", "Pack"), ("bottle", "Bottle"), ("tube", "Tube"), ("set", "Set"),
]
GST_RATE_CHOICES = [(Decimal("0"), "0%"), (Decimal("5"), "5%"), (Decimal("18"), "18%"), (Decimal("40"), "40%")]


# Type of business an item name / category belongs to, so a salon does not see restaurant items
BUSINESS_TYPES = [
    ("beauty", "Salon / beauty / wellness"),
    ("food", "Restaurant / food"),
    ("general", "All businesses"),
]
BEAUTY_WORDS = ("salon", "saloon", "nail", "beauty", "parlour", "parlor", "spa", "barber", "hair", "makeup",
                "gym", "fitness", "yoga", "massage", "cosmetic")
FOOD_WORDS = ("restaurant", "cafe", "dhaba", "food", "catering", "bakery", "kitchen", "hotel")


def business_type_of(branch):
    """'beauty', 'food' or 'general' for a branch (from its GST service type, else its category name)."""
    sac = (getattr(branch, "sac_code", "") or "").strip()
    if sac.startswith("99972"):
        return "beauty"
    if sac == "996331":
        return "food"
    name = (branch.services_category.name if branch.services_category_id else "").lower()
    if any(w in name for w in FOOD_WORDS):
        return "food"
    if any(w in name for w in BEAUTY_WORDS):
        return "beauty"
    return "general"


class SupplierDirectory(models.Model):
    """Shared list of suppliers (business details only), shown in the 'Add supplier' dropdown to shops
    of the same type in the same city. Never stores who buys from them or at what rate."""
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=15, blank=True, verbose_name="GSTIN")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    items_supplied = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=10, choices=BUSINESS_TYPES, default="general")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name = "Supplier directory entry"
        verbose_name_plural = "Supplier directory"

    def __str__(self):
        return f"{self.name}{' - ' + self.city if self.city else ''}"


class Supplier(models.Model):
    """The business's own copy of a supplier (editable). Linked to the shared directory entry."""
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="suppliers")
    directory = models.ForeignKey(SupplierDirectory, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="copies")
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True, help_text="Mobile number for WhatsApp, e.g. 9876543210")
    email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=15, blank=True, verbose_name="GSTIN")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    items_supplied = models.CharField(max_length=255, blank=True, help_text="e.g. Gel polish, nail files, acetone")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return self.name

    @property
    def whatsapp_link(self):
        digits = "".join(ch for ch in (self.whatsapp or self.phone or "") if ch.isdigit())
        if len(digits) == 10:
            digits = "91" + digits
        return f"https://wa.me/{digits}" if len(digits) >= 11 else ""


# Starting list of categories (the owner can add more from the "Add item" form)
DEFAULT_CATEGORIES = [
    ("Nail products", "beauty"), ("Hair care", "beauty"), ("Skin care", "beauty"), ("Makeup", "beauty"),
    ("Spa & massage", "beauty"), ("Tools & equipment", "beauty"), ("Disposables (gloves, towels, foils)", "beauty"),
    ("Groceries", "food"), ("Vegetables & fruits", "food"), ("Dairy", "food"), ("Meat & seafood", "food"),
    ("Spices & masala", "food"), ("Oil & ghee", "food"), ("Beverages", "food"), ("Packaging", "food"),
    ("Gas & fuel", "food"),
    ("Cleaning & hygiene", "general"), ("Stationery", "general"), ("Other", "general"),
]


class ItemCategory(models.Model):
    """Common list of item categories shown in the 'Category' dropdown."""
    name = models.CharField(max_length=60, unique=True)
    business_type = models.CharField(max_length=10, choices=BUSINESS_TYPES, default="general")
    # Account code for purchases of this category (future accounting); default 5001 Purchases - stock items
    account = models.ForeignKey("ledger.Account", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="item_categories", verbose_name="Purchase account code")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Item categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.account_id is None:  # link new categories to a default account code
            from ledger.models import Account
            self.account = Account.objects.filter(code="5001").first()
        super().save(*args, **kwargs)


class ItemName(models.Model):
    """Common list of item names shown in the 'Add item' dropdown (like service names).
    A business picks one, or adds a new name, which is saved here for everyone."""
    name = models.CharField(max_length=150, unique=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="pcs", help_text="Usual unit")
    category = models.CharField(max_length=60, blank=True)
    business_type = models.CharField(max_length=10, choices=BUSINESS_TYPES, default="general")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="stock_items")
    master = models.ForeignKey(ItemName, on_delete=models.SET_NULL, null=True, blank=True, related_name="items")
    name = models.CharField(max_length=150, help_text="e.g. Gel polish - Red 15 ml")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="pcs")
    category = models.CharField(max_length=60, blank=True, help_text="e.g. Nail products, Cleaning, Groceries")
    hsn_code = models.CharField(max_length=8, blank=True, verbose_name="HSN code")
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0,
                                    help_text="Alert when stock falls below this quantity")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.name} ({self.unit})"


class StockBalance(models.Model):
    """Current stock of an item at a branch (stored; updated by every stock move)."""
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="stock_balances")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="balances")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    avg_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0, help_text="Weighted average cost per unit")
    is_low = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "item")
        ordering = ["item__name"]

    def __str__(self):
        return f"{self.item} @ {self.branch}: {self.quantity}"


class Receipt(models.Model):
    """A purchase bill: goods received from a supplier."""
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="receipts")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="receipts")
    bill_number = models.CharField(max_length=40, help_text="Supplier's bill / invoice number")
    bill_date = models.DateField(default=datetime.date.today)
    rates_include_gst = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)
    bill_file = models.FileField(upload_to="purchase_bills/", blank=True, help_text="Photo or PDF of the bill (optional)")
    # Stored totals
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_value = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Amount added to stock")
    itc_claimable = models.BooleanField(default=False, help_text="Branch can claim input tax credit on this bill")
    supplier_gstin = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-bill_date", "-id"]

    def __str__(self):
        return f"{self.supplier} bill {self.bill_number} ({self.bill_date})"


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="receipt_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    rate = models.DecimalField(max_digits=12, decimal_places=2, help_text="Rate per unit as on the bill")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"


class StockMove(models.Model):
    """Ledger of every stock change (receipt +, issue -, adjustment +/-)."""
    KIND_CHOICES = [("receipt", "Receipt"), ("issue", "Issue (used)"), ("adjust", "Adjustment")]
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="stock_moves")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="moves")
    date = models.DateField(default=datetime.date.today)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, help_text="+ in, - out")
    value = models.DecimalField(max_digits=14, decimal_places=2, help_text="+ in, - out (at cost)")
    receipt_line = models.ForeignKey(ReceiptLine, on_delete=models.CASCADE, null=True, blank=True, related_name="moves")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity} {self.item.name}"


class StockCount(models.Model):
    """Closing stock 'as at' a date. Items used in the period = book stock - counted stock
    (no daily entry needed). All figures are stored.
    Staff can count (status 'pending'); the branch admin reviews and approves (or sends it back)."""
    STATUS_CHOICES = [("pending", "Waiting for approval"), ("returned", "Sent back"), ("approved", "Approved")]
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="stock_counts")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="approved")
    counted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="stock_counts_counted")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="stock_counts_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True, help_text="Why it was sent back")
    as_at = models.DateField(default=datetime.date.today, verbose_name="Closing stock as at")
    notes = models.CharField(max_length=255, blank=True)
    closing_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    used_value = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     help_text="Cost of items used since the last count (negative = extra found)")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-as_at", "-id"]
        unique_together = ("branch", "as_at")

    def __str__(self):
        return f"Closing stock {self.branch} as at {self.as_at}"


class StockCountLine(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="count_lines")
    book_qty = models.DecimalField(max_digits=14, decimal_places=3, default=0, help_text="As per purchases and last count")
    counted_qty = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True,
                                      help_text="Empty = not counted by staff (book stock is used)")
    used_qty = models.DecimalField(max_digits=14, decimal_places=3, default=0, help_text="book - counted")
    avg_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    closing_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    used_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["item__name"]

    def __str__(self):
        return f"{self.item.name}: {self.counted_qty}"
