from django.contrib import admin
from .models import Queue, Token

@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
        list_display = ['id', 'branch', 'date', 'is_active']
        # search_fields = ['service__name']
        # list_filter = ['date', 'is_active']
        # ordering = ['-date']
        
        
@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'guest', 'token_number', 'status', 'final_price', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    ordering = ['-created_at']