from django.contrib import admin

# Register your models here.

from .models import Organization, Branch, Address, Registration, Service,Service_Name,Service_Category

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "phone", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
    ordering = ("-created_at",)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "name", "address", "is_gst_registered", "gstin", "gst_percentage")
    search_fields = ("name", "organization__name", "gstin")
    list_filter = ("organization", "is_gst_registered")

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "organization", "line1", "city")
    search_fields = ("line1", "city")
    list_filter = ("branch", "organization")

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "organization", "registration_type")
    search_fields = ("registration_type",)
    list_filter = ("branch", "organization")

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "name")
    search_fields = ("name","branch__name")
    list_filter = ("branch",)
    ordering = ("name",)
    
@admin.register(Service_Name)
class ServiceNameAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)    
    
@admin.register(Service_Category)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)
    