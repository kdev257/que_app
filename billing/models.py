from django.conf import settings
from django.db import models


class Invoice(models.Model):
    """
    A saved invoice. Every amount is calculated once (when the invoice is
    generated) and stored here, so templates only display stored values.
    Customer and branch details are copied in, so the invoice never changes
    even if the branch or customer is edited later.
    """
    SOURCE_CHOICES = [
        ('service', 'Service'),
        ('restaurant', 'Restaurant'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('online', 'Online (QuickQueue)'),
        ('other', 'Other'),
    ]

    # GST rule 46: max 16 characters, consecutive serial, unique for the financial year (per branch series)
    invoice_number = models.CharField(max_length=40, blank=True)
    financial_year = models.CharField(max_length=5, blank=True, help_text="e.g. 26-27")
    serial_number = models.PositiveIntegerField(default=0)
    token = models.OneToOneField('queues.Token', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    branch = models.ForeignKey('organization.Branch', on_delete=models.PROTECT, related_name='invoices')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='service')
    token_number = models.IntegerField(default=0)
    service_date = models.DateField(null=True, blank=True)

    # Seller (branch) snapshot
    seller_name = models.CharField(max_length=255)
    seller_address = models.TextField(blank=True)
    seller_phone = models.CharField(max_length=20, blank=True)
    seller_email = models.EmailField(blank=True)

    # Customer snapshot
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    customer_guest = models.ForeignKey('login.Guest', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')

    # GST
    is_gst_invoice = models.BooleanField(default=False)
    gstin = models.CharField(max_length=15, blank=True)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    prices_include_gst = models.BooleanField(default=True)
    # Place of supply (stored once; reports and GSTR-1 read these)
    TAX_TYPE_CHOICES = [
        ('intra', 'CGST + SGST'),
        ('intra_ut', 'CGST + UTGST'),
        ('inter', 'IGST'),
        ('none', 'No GST'),
    ]
    supplier_state_code = models.CharField(max_length=2, blank=True)
    place_of_supply_code = models.CharField(max_length=2, blank=True)
    place_of_supply_name = models.CharField(max_length=60, blank=True)
    tax_type = models.CharField(max_length=10, choices=TAX_TYPE_CHOICES, blank=True)
    customer_gstin = models.CharField(max_length=15, blank=True)
    customer_business_name = models.CharField(max_length=150, blank=True)

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Sum of item amounts")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="SGST or UTGST rate")
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    utgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    booking_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Booking fee (before its GST)")
    booking_fee_gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    booking_fee_gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    booking_fee_tax_type = models.CharField(max_length=10, choices=TAX_TYPE_CHOICES, blank=True)
    booking_fee_cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    booking_fee_sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="SGST or UTGST")
    booking_fee_igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_gstin = models.CharField(max_length=15, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cashback_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=30, blank=True)
    payment_status_display = models.CharField(max_length=50, blank=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, blank=True)
    # Total of credit notes issued against this invoice (updated when a credit note is made)
    credited_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices_created')
    email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'invoice_number'], name='unique_invoice_number_per_branch'),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_name} (Rs. {self.total_amount})"

    @property
    def branch_amount(self):
        """Branch's own part of the bill (taxable + GST), without QuickQueue's booking fee."""
        return self.taxable_amount + self.gst_amount

    @property
    def can_credit_amount(self):
        return self.branch_amount - self.credited_amount

    @staticmethod
    def _tax_lines(tax_type, cgst, sgst, utgst, igst):
        if tax_type == 'inter':
            return [("IGST", igst)]
        if tax_type == 'intra_ut':
            return [("CGST", cgst), ("UTGST", utgst)]
        return [("CGST", cgst), ("SGST", sgst)]

    @property
    def tax_lines(self):
        """GST rows to print, e.g. [('CGST', 9.00), ('SGST', 9.00)] or [('IGST', 18.00)] (stored values only)."""
        return self._tax_lines(self.tax_type, self.cgst_amount, self.sgst_amount, self.utgst_amount, self.igst_amount)

    @property
    def tax_lines_with_rate(self):
        """[(label, rate, amount)] e.g. [('CGST', 2.50, 25.00), ('SGST', 2.50, 25.00)]."""
        rates = {"CGST": self.cgst_rate, "SGST": self.sgst_rate, "UTGST": self.sgst_rate, "IGST": self.igst_rate}
        return [(label, rates.get(label, 0), amount) for label, amount in self.tax_lines]

    @property
    def fee_tax_lines(self):
        if self.booking_fee_tax_type in ('', 'none'):  # invoices made before the split was stored
            return [("GST", self.booking_fee_gst_amount)]
        return self._tax_lines(self.booking_fee_tax_type, self.booking_fee_cgst, self.booking_fee_sgst,
                               self.booking_fee_sgst, self.booking_fee_igst)


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    sac_code = models.CharField(max_length=8, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.description}"


class DocumentSequence(models.Model):
    """Last number used per branch, document type and financial year (gives consecutive serial numbers)."""
    DOC_TYPES = [('invoice', 'Invoice'), ('credit_note', 'Credit note')]
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='document_sequences')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    financial_year = models.CharField(max_length=5)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('branch', 'doc_type', 'financial_year')

    def __str__(self):
        return f"{self.branch} {self.doc_type} {self.financial_year}: {self.last_number}"


class CreditNote(models.Model):
    """Reduces an invoice (refund, cancelled bill, later discount). Amounts are stored once."""
    REASON_CHOICES = [
        ('cancelled', 'Bill cancelled'),
        ('refund', 'Refund to customer'),
        ('discount', 'Discount after billing'),
        ('error', 'Correction of mistake'),
        ('other', 'Other'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    branch = models.ForeignKey('organization.Branch', on_delete=models.PROTECT, related_name='credit_notes')
    number = models.CharField(max_length=40)
    financial_year = models.CharField(max_length=5)
    serial_number = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    tax_type = models.CharField(max_length=10, blank=True)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    utgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='credit_notes_created')

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'number'], name='unique_credit_note_number_per_branch'),
        ]

    def __str__(self):
        return f"{self.number} against {self.invoice.invoice_number} (Rs. {self.total_amount})"

    @property
    def tax_lines(self):
        return Invoice._tax_lines(self.tax_type, self.cgst_amount, self.sgst_amount, self.utgst_amount, self.igst_amount)

