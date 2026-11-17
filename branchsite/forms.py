from django import forms
from django.utils.text import slugify

from .images import check_size
from .models import BranchSite, SiteOffer, SitePhoto, SiteSection

RESERVED_SLUGS = {"admin", "static", "media", "new", "edit"}


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = BranchSite
        fields = ["is_published", "slug", "theme", "tagline", "about", "hours_note", "logo", "banner",
                  "show_offers", "show_services", "show_gallery", "show_reviews", "show_hours",
                  "show_location", "show_contact"]
        labels = {
            "is_published": "Publish my website",
            "slug": "Page address",
            "hours_note": "Note about timings",
            "banner": "Banner photo",
        }
        widgets = {
            "theme": forms.RadioSelect,
            "about": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])[:80]
        if not slug or slug in RESERVED_SLUGS:
            raise forms.ValidationError("Please choose another page address.")
        if BranchSite.objects.filter(slug=slug).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("This address is already taken. Please choose another.")
        return slug

    def clean_logo(self):
        return check_size(self.cleaned_data.get("logo"))

    def clean_banner(self):
        return check_size(self.cleaned_data.get("banner"))


class OfferForm(forms.ModelForm):
    class Meta:
        model = SiteOffer
        fields = ["title", "details", "discount_type", "discount_value", "min_bill_amount", "max_discount",
                  "start_date", "valid_till"]
        labels = {
            "title": "Offer", "discount_type": "Kind of offer", "discount_value": "Discount",
            "min_bill_amount": "Minimum bill (₹)", "max_discount": "Maximum discount (₹, optional)",
            "start_date": "Starts on (optional)", "valid_till": "Ends on (optional)",
        }
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}),
                   "valid_till": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        kind, value = cleaned.get("discount_type"), cleaned.get("discount_value") or 0
        if kind in ("percent", "flat") and value <= 0:
            self.add_error("discount_value", "Enter the discount, e.g. 10.")
        if kind == "percent" and value > 100:
            self.add_error("discount_value", "A % discount cannot be more than 100.")
        start, end = cleaned.get("start_date"), cleaned.get("valid_till")
        if start and end and end < start:
            self.add_error("valid_till", "End date must be after the start date.")
        return cleaned


class PhotoForm(forms.ModelForm):
    class Meta:
        model = SitePhoto
        fields = ["image", "caption"]
        labels = {"image": "Photo", "caption": "Caption (optional)"}

    def clean_image(self):
        return check_size(self.cleaned_data.get("image"))


class SectionForm(forms.ModelForm):
    class Meta:
        model = SiteSection
        fields = ["title", "body", "image", "sort_order", "is_active"]
        labels = {"title": "Section title", "body": "Text", "image": "Photo (optional)",
                  "sort_order": "Order", "is_active": "Show on website"}
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}

    def clean_image(self):
        return check_size(self.cleaned_data.get("image"))
