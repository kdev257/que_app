import datetime

from django.db import models
from django.core.exceptions import ValidationError
# Create your models here.



from .service_styles import GROUPS as SERVICE_ICON_GROUPS
from .gst import RULE_CHOICES, RULE_GENERAL, STATE_CHOICES, gstin_error, state_name


class Organization(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Branch(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,related_name="branches")
    services_category = models.ForeignKey('Service_Category', on_delete=models.SET_NULL, blank=True, null=True, related_name="services_offered")
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True, null=True,help_text="recommended to be filled accurately for better service matching")
    locality = models.CharField(max_length=100, blank=True, null=True,help_text="recommended to be filled accurately for better service matching")
    state= models.CharField(max_length=100, blank=True, null=True)
    # GST state code (e.g. 27 = Maharashtra). Decides CGST+SGST vs IGST. The "state" text above is filled from it.
    gst_state_code = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, verbose_name="State",
                                      help_text="State where this branch is located (as per GST registration)")
    country = models.CharField(max_length=100,blank=True, null=True)
    pin_code = models.CharField(max_length=20, blank=True, null=True,help_text="recommended to be filled accurately for better service matching")
    phone = models.CharField(max_length=20, blank=True, null=True,help_text="recommended to be filled accurately for better service matching")
    email = models.EmailField(blank=True, null=True,help_text="recommended to be filled accurately so that customers can contact in case of any issues")
    number_of_employees = models.IntegerField(blank=True, null=True,help_text="recommended to be filled accurately to calculate average waiting time for services",default=1)
    opening_time = models.TimeField(default=datetime.time(8, 0),blank=True,null=True,help_text="Format: 8:00 AM" )    
    closing_time = models.TimeField(default=datetime.time(21, 0),blank=True,null=True,help_text="Format: 9:00 PM" )
    is_open = models.BooleanField(default=False)
    offers_delivery = models.BooleanField(default=False, help_text="Check if this branch offers home delivery")
    # Shown to customers only after the superadmin approves it
    # Branches added in Admin are live at once; branches added via the Business Workspace start as pending
    is_approved = models.BooleanField(default=True, help_text="Approved by QuickQueue. Only approved branches are shown to customers.")
    # Ratings: stored here and updated whenever a review is saved (not calculated on every page load)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    # Social media / contact links shown on the branch page
    website_url = models.URLField(blank=True, help_text="e.g. https://www.mysalon.in")
    instagram_url = models.URLField(blank=True, help_text="e.g. https://instagram.com/mysalon")
    facebook_url = models.URLField(blank=True, help_text="e.g. https://facebook.com/mysalon")
    google_maps_url = models.URLField(blank=True, help_text="Google Maps / Google reviews link of the branch")
    whatsapp_number = models.CharField(max_length=15, blank=True, help_text="Mobile number for WhatsApp chat, e.g. 9876543210")

    @property
    def whatsapp_link(self):
        digits = "".join(ch for ch in (self.whatsapp_number or "") if ch.isdigit())
        if len(digits) == 10:
            digits = "91" + digits  # Indian mobile number without country code
        return f"https://wa.me/{digits}" if len(digits) >= 11 else ""

    @property
    def has_social_links(self):
        return any([self.website_url, self.instagram_url, self.facebook_url, self.google_maps_url, self.whatsapp_link])
    # GST details (used on invoices)
    is_gst_registered = models.BooleanField(default=False, help_text="Tick if this branch is registered under GST")
    gstin = models.CharField(max_length=15, blank=True, null=True, help_text="15-character GSTIN (required if GST registered)")
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=18.00, help_text="Total GST % (CGST + SGST together, or IGST)")
    prices_include_gst = models.BooleanField(default=True, help_text="Tick if service/menu prices already include GST")
    # Restaurants inside a hotel with room tariff above Rs 7,500/day (or hotel that opted in): 18% with ITC
    specified_premises = models.BooleanField(default=False, verbose_name="Restaurant in a hotel (specified premises)",
                                             help_text="Tick only if this restaurant is in a hotel where any room was above Rs 7,500 per day last year, or the hotel opted for 18% with ITC")
    # Type of service for GST (chosen by the owner in GST settings). Decides SAC on invoices and the legal rate.
    sac_code = models.CharField(max_length=8, blank=True, verbose_name="Type of service (SAC code)")
    # Can this branch claim GST paid on purchases? Stored when GST settings are saved.
    itc_allowed = models.BooleanField(default=True, verbose_name="Input tax credit allowed")
    # Invoice number series: PREFIX/26-27/00001 (GST rule: max 16 characters, new series every financial year)
    invoice_prefix = models.CharField(max_length=4, blank=True,
                                      help_text="1-4 letters/digits, e.g. DST. Invoice numbers look like DST/26-27/00001.")

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.name} - {self.organization.name}"
    
    def clean(self):
        if self.opening_time and self.closing_time:
            if self.opening_time >= self.closing_time:
                raise ValidationError("Closing time must be after opening time.")
        # Plain (non-field) errors, so they show on any form, even one without the GST fields
        if self.is_gst_registered:
            if not self.gst_state_code:
                raise ValidationError("Please select the state of this branch (needed for GST).")
            error = gstin_error(self.gstin, self.gst_state_code)
            if error:
                raise ValidationError(f"GSTIN: {error}")

    def save(self, *args, **kwargs):
        if self.gst_state_code:
            self.state = state_name(self.gst_state_code)  # keep the text field in step
        super().save(*args, **kwargs)

    @staticmethod
    def suggest_prefix(name, organization_id, exclude_id=None):
        """Initials of the name (e.g. 'Destello Nail Studio' -> 'DNS'), unique within the organization."""
        words = ["".join(ch for ch in w if ch.isalnum()) for w in (name or "").upper().split()]
        words = [w for w in words if w]
        base = "".join(w[0] for w in words)[:3] if len(words) > 1 else (words[0][:3] if words else "INV")
        base = base or "INV"
        taken = set(Branch.objects.filter(organization_id=organization_id).exclude(id=exclude_id)
                    .exclude(invoice_prefix="").values_list("invoice_prefix", flat=True))
        if base not in taken:
            return base
        for n in range(2, 10):
            if f"{base}{n}" not in taken:
                return f"{base}{n}"
        return f"B{exclude_id or ''}"[:4]

    def get_invoice_prefix(self):
        """Return the invoice prefix, creating and saving one the first time."""
        if not self.invoice_prefix:
            self.invoice_prefix = Branch.suggest_prefix(self.name, self.organization_id, self.id)
            Branch.objects.filter(pk=self.pk).update(invoice_prefix=self.invoice_prefix)
        return self.invoice_prefix



class Address(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, blank=True, null=True,related_name="addresses")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True,related_name="addresses")    
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.line1}, {self.city}"
    
    def clean(self):
            if not self.organization and not self.branch:
                raise ValidationError("Address must belong to either organization or branch.")
    
    
    
class Registration(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    registration_type = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    document = models.FileField(upload_to='registrations/', blank=True, null=True)

    def __str__(self):
        return f"{self.registration_type} - {self.registration_number}"
    
    def clean(self):
            if not self.organization and not self.branch:
                raise ValidationError("Registration must belong to either organization or branch.")
    

class Service_Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    # GST place of supply rule (IGST Act s.12): salons, restaurants, gyms, clinics -> "where performed"
    place_of_supply_rule = models.CharField(max_length=20, choices=RULE_CHOICES, default=RULE_GENERAL,
                                            verbose_name="GST place of supply rule")
    sac_code = models.CharField(max_length=8, blank=True, verbose_name="SAC code",
                                help_text="Printed on invoices, e.g. 999721 hair, 999722 nails/beauty, 996331 restaurant")
    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18,
                                           verbose_name="Usual GST %", help_text="Salon/beauty/spa/gym/restaurant: 5% (since 22-09-2025)")
    itc_allowed = models.BooleanField(default=True, verbose_name="Input tax credit allowed",
                                      help_text="Untick for 5% services where GST paid on purchases cannot be claimed")
    # Account code for sales of this business type (future accounting): 4001 services / 4002 food
    sales_account = models.ForeignKey("ledger.Account", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="service_categories", verbose_name="Sales account code")

    def save(self, *args, **kwargs):
        if self.sales_account_id is None:
            from ledger.models import Account
            food = any(w in (self.name or "").lower() for w in ("restaurant", "cafe", "dhaba", "food", "catering", "bakery"))
            self.sales_account = Account.objects.filter(code="4002" if food else "4001").first()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"
    
class Service_Name(models.Model):
    name = models.CharField(max_length=255, unique=True)
    # Shown on service cards. Set automatically from the name when created; can be changed in Admin.
    icon = models.CharField(max_length=40, blank=True, help_text="Bootstrap icon class, e.g. bi-scissors")
    icon_group = models.CharField(max_length=20, choices=SERVICE_ICON_GROUPS, default="other", help_text="Colour group of the icon")
    
    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        if not self.icon:
            from .service_styles import guess_style
            self.icon, self.icon_group = guess_style(self.name)
        super().save(*args, **kwargs)

class Service(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE,related_name="service_branch")
    name = models.ForeignKey(Service_Name, on_delete=models.CASCADE,related_name="services")
    category = models.ForeignKey(Service_Category, on_delete=models.CASCADE,related_name="services_cat", blank=True, null=True)
    average_time_minutes = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, max_length=500, help_text="Short description shown to customers, e.g. 'Includes wash and blow-dry'")
    sac_code = models.CharField(max_length=8, blank=True, verbose_name="SAC code",
                                help_text="Leave empty to use the SAC code of the business type")
    
    class Meta:
        ordering = ["name"]
        unique_together = ("branch", "name")

    def __str__(self):
        return f"{self.name} - {self.branch.name}"