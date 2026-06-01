from django.contrib import admin

# Register your models here.
from .models import Customer, Promotion, PromotionDiscount, PlatformFee

class PromotionDiscountInline(admin.StackedInline):
    model = PromotionDiscount
    extra = 1
    max_num = 1

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'created_at')
    search_fields = ('name', 'phone', 'email')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'slot', 'start_date', 'end_date', 'is_active')
    list_filter = ('slot', 'is_active', 'start_date', 'end_date')
    search_fields = ('title',)
    ordering = ('-start_date',)
    inlines = [PromotionDiscountInline]

@admin.register(PromotionDiscount)
class PromotionDiscountAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'discount_percentage', 'cashback_amount', 'is_active')
    list_filter = ('is_active',)

@admin.register(PlatformFee)
class PlatformFeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'fee_logged_in', 'fee_guest', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('name',)


    
