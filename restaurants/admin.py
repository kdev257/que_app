from django.contrib import admin
from organization.models import Branch
from .models import (
    MenuCategoryName, MenuCategory, GlobalMenuItem, MenuItem, Table, RestaurantOrder, 
    RestaurantOrderItem, RestaurantLandmark, Highway, HighwayBranch, HighwaySegment
)

class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.register(MenuCategoryName)
class MenuCategoryNameAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(GlobalMenuItem)
class GlobalMenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_veg')
    list_filter = ('is_veg',)
    search_fields = ('name',)


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch')
    list_filter = ('branch',)
    inlines = [MenuItemInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch":
            # Only show branches belonging to the 'restaurant' category
            kwargs["queryset"] = Branch.objects.filter(services_category__name__iexact='restaurant')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available', 'is_veg')
    list_filter = ('category__branch', 'is_available', 'is_veg')
    search_fields = ('name', 'description')


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'branch', 'capacity', 'is_occupied', 'is_active')
    list_filter = ('branch', 'is_occupied', 'is_active')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch":
            # Only show branches belonging to the 'restaurant' category
            kwargs["queryset"] = Branch.objects.filter(services_category__name__iexact='restaurant')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RestaurantOrderItemInline(admin.TabularInline):
    model = RestaurantOrderItem
    extra = 0


@admin.register(RestaurantOrder)
class RestaurantOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'branch', 'table', 'status', 'order_type', 'estimated_prep_time_minutes', 'created_at')
    list_filter = ('branch', 'status', 'order_type')
    inlines = [RestaurantOrderItemInline]


@admin.register(RestaurantLandmark)
class RestaurantLandmarkAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch')
    list_filter = ('branch',)
    search_fields = ('name',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch":
            # Only show branches belonging to the 'restaurant' category
            kwargs["queryset"] = Branch.objects.filter(services_category__name__iexact='restaurant')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Highway)
class HighwayAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_point', 'end_point')


@admin.register(HighwayBranch)
class HighwayBranchAdmin(admin.ModelAdmin):
    list_display = ('branch', 'highway', 'segment', 'milestone_km', 'direction_of_travel', 'is_exclusive', 'exclusivity_range_km')
    list_filter = ('highway', 'is_exclusive', 'direction_of_travel')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch":
            # Only show branches belonging to the 'restaurant' category
            kwargs["queryset"] = Branch.objects.filter(services_category__name__iexact='restaurant')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(HighwaySegment)
class HighwaySegmentAdmin(admin.ModelAdmin):
    list_display = ('highway', 'start_place', 'end_place', 'start_km', 'end_km')
    list_filter = ('highway',)
    search_fields = ('start_place', 'end_place')

