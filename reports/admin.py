from django.contrib import admin

from .models import ProfitLossLine, ProfitLossReport


class ProfitLossLineInline(admin.TabularInline):
    model = ProfitLossLine
    extra = 0
    can_delete = False
    readonly_fields = ("label", "account_code", "amount")


@admin.register(ProfitLossReport)
class ProfitLossReportAdmin(admin.ModelAdmin):
    list_display = ("organization", "branch", "period_from", "period_to", "net_sales", "net_profit", "created_at")
    list_filter = ("organization", "branch")
    inlines = [ProfitLossLineInline]
