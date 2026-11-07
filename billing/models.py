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

    invoice_number = models.CharField(max_length=40, unique=True, blank=True)
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

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Sum of item amounts")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    booking_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Booking fee (before its GST)")
    booking_fee_gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    booking_fee_gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_gstin = models.CharField(max_length=15, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cashback_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=30, blank=True)
    payment_status_display = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices_created')
    email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_name} (Rs. {self.total_amount})"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.description}"
