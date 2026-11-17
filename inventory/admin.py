from django.contrib import admin

from .models import (Item, ItemCategory, ItemName, Receipt, ReceiptLine, StockBalance, StockCount, StockCountLine,
                     StockMove, Supplier, SupplierDirectory)


@admin.register(SupplierDirectory)
class SupplierDirectoryAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "business_type", "phone", "gstin")
    list_filter = ("business_type", "city")
    list_editable = ("business_type",)
    search_fields = ("name", "city", "items_supplied", "gstin")


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business_type", "account")
    list_editable = ("business_type", "account")
    list_filter = ("business_type",)
    search_fields = ("name",)


@admin.register(ItemName)
class ItemNameAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "category", "business_type")
    list_editable = ("business_type",)
    list_filter = ("business_type",)
    search_fields = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "phone", "gstin", "city", "is_active")
    search_fields = ("name", "gstin", "items_supplied")
    list_filter = ("organization", "is_active")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "unit", "category", "min_stock", "is_active")
    search_fields = ("name", "category")
    list_filter = ("organization", "is_active")


class ReceiptLineInline(admin.TabularInline):
    model = ReceiptLine
    extra = 0
    can_delete = False
    readonly_fields = ("item", "quantity", "rate", "gst_rate", "taxable_amount", "gst_amount", "total_amount", "stock_value")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("bill_number", "supplier", "branch", "bill_date", "total_amount", "itc_claimable")
    list_filter = ("branch", "itc_claimable")
    search_fields = ("bill_number", "supplier__name")
    inlines = [ReceiptLineInline]


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("item", "branch", "quantity", "value", "avg_cost", "is_low")
    list_filter = ("branch", "is_low")


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("date", "branch", "item", "kind", "quantity", "value")
    list_filter = ("branch", "kind")


class StockCountLineInline(admin.TabularInline):
    model = StockCountLine
    extra = 0
    can_delete = False
    readonly_fields = ("item", "book_qty", "counted_qty", "used_qty", "avg_cost", "closing_value", "used_value")


@admin.register(StockCount)
class StockCountAdmin(admin.ModelAdmin):
    list_display = ("branch", "as_at", "closing_value", "used_value")
    list_filter = ("branch",)
    inlines = [StockCountLineInline]
