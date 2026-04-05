from django.contrib import admin
from .models import User,UserProfile,State,City
# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'is_staff')
    
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user','address', 'city', 'state')
    search_fields = ('user__username', 'first_name', 'last_name')
    
@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    
@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    search_fields = ('name', 'state__name')
    