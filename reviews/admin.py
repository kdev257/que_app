from django.contrib import admin

from .models import Review
from .services import update_branch_rating


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("created_at", "branch", "rating", "display_name", "is_hidden", "comment")
    list_filter = ("is_hidden", "rating", "branch")
    search_fields = ("display_name", "comment", "branch__name")
    actions = ["hide_reviews", "show_reviews"]

    def _refresh(self, queryset):
        for branch in {r.branch for r in queryset.select_related("branch")}:
            update_branch_rating(branch)

    @admin.action(description="Hide selected reviews")
    def hide_reviews(self, request, queryset):
        queryset.update(is_hidden=True)
        self._refresh(queryset)

    @admin.action(description="Show selected reviews")
    def show_reviews(self, request, queryset):
        queryset.update(is_hidden=False)
        self._refresh(queryset)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        update_branch_rating(obj.branch)
