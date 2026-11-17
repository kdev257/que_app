from django.contrib import admin

from .models import CreditNote, DocumentSequence, Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("description", "sac_code", "quantity", "unit_price", "amount")
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "branch", "customer_name", "total_amount", "is_gst_invoice", "payment_status", "email_sent", "created_at")
    list_filter = ("branch", "source", "is_gst_invoice", "payment_status", "created_at")
    search_fields = ("invoice_number", "customer_name", "customer_email", "customer_phone")
    inlines = [InvoiceItemInline]


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("number", "invoice", "branch", "reason", "total_amount", "created_at")
    list_filter = ("branch", "reason", "financial_year")
    search_fields = ("number", "invoice__invoice_number")


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("branch", "doc_type", "financial_year", "last_number")
    list_filter = ("doc_type", "financial_year")
