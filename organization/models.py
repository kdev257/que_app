import datetime

from django.db import models
from django.core.exceptions import ValidationError
# Create your models here.



from .service_styles import GROUPS as SERVICE_ICON_GROUPS


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
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=18.00, help_text="Total GST % (split equally into CGST + SGST)")
    prices_include_gst = models.BooleanField(default=True, help_text="Tick if service/menu prices already include GST")

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.name} - {self.organization.name}"
    
    def clean(self):
        if self.opening_time and self.closing_time:
            if self.opening_time >= self.closing_time:
                raise ValidationError("Closing time must be after opening time.")
        if self.is_gst_registered and not (self.gstin and len(self.gstin.strip()) == 15):
            raise ValidationError({"gstin": "A valid 15-character GSTIN is required when GST registered."})



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
    
    class Meta:
        ordering = ["name"]
        unique_together = ("branch", "name")

    def __str__(self):
        return f"{self.name} - {self.branch.name}"