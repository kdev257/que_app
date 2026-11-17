from django.contrib import admin

from .models import Account, AccountMapping


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "group", "is_active")
    list_editable = ("name", "group", "is_active")
    list_filter = ("account_type", "group", "is_active")
    search_fields = ("code", "name")


@admin.register(AccountMapping)
class AccountMappingAdmin(admin.ModelAdmin):
    list_display = ("key", "account")
    list_editable = ("account",)
