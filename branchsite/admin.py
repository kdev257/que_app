from django.contrib import admin

from .models import BranchSite, SiteOffer, SitePhoto, SiteSection


class SiteOfferInline(admin.TabularInline):
    model = SiteOffer
    extra = 0


class SitePhotoInline(admin.TabularInline):
    model = SitePhoto
    extra = 0


class SiteSectionInline(admin.TabularInline):
    model = SiteSection
    extra = 0


@admin.register(BranchSite)
class BranchSiteAdmin(admin.ModelAdmin):
    list_display = ("branch", "slug", "theme", "is_published", "updated_at")
    list_filter = ("is_published", "theme")
    search_fields = ("branch__name", "slug")
    inlines = [SiteOfferInline, SitePhotoInline, SiteSectionInline]
