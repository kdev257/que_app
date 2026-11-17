from django.contrib import admin

from .models import Expense, ExpenseCategory, ExpenseMonthTotal


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "account")
    list_editable = ("account",)
    search_fields = ("name",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "branch", "category", "total_amount", "expense_value", "itc_claimable", "payment_mode")
    list_filter = ("branch", "category", "month")
    readonly_fields = ("taxable_amount", "gst_amount", "total_amount", "itc_claimable", "expense_value", "month")


@admin.register(ExpenseMonthTotal)
class ExpenseMonthTotalAdmin(admin.ModelAdmin):
    list_display = ("branch", "month", "category", "total_amount", "expense_value", "count")
    list_filter = ("branch", "month")
