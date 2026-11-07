from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("description", "quantity", "unit_price", "amount")
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "branch", "customer_name", "total_amount", "is_gst_invoice", "payment_status", "email_sent", "created_at")
    list_filter = ("branch", "source", "is_gst_invoice", "payment_status", "created_at")
    search_fields = ("invoice_number", "customer_name", "customer_email", "customer_phone")
    inlines = [InvoiceItemInline]
