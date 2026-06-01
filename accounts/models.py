# Create your models here.

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"
    
class Promotion(models.Model):
    SLOT_CHOICES = [
        ('popup', 'Login Pop-up'),
        ('hero', 'Main Dashboard Banner'),
        ('sidebar', 'Sidebar Tile'),
    ]

    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='promos/')
    link = models.URLField(help_text="Where should the button lead?")
    slot = models.CharField(max_length=20, choices=SLOT_CHOICES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def is_currently_running(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    def __str__(self):
        return f"{self.get_slot_display()}: {self.title}"


class PromotionDiscount(models.Model):
    promotion = models.OneToOneField(Promotion, on_delete=models.CASCADE, related_name='discount')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Discount percentage to apply to the cart total (e.g., 10.00 for 10%)")
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Cashback amount to reward after service completion")
    is_active = models.BooleanField(default=True)

    def is_valid(self):
        return self.is_active and self.promotion.is_currently_running()

    def __str__(self):
        return f"Discount for {self.promotion.title}"


class PlatformFee(models.Model):
    name = models.CharField(max_length=100, default="Booking Fee")
    fee_logged_in = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee for registered / logged-in users")
    fee_guest = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee for guest checkouts")
    start_date = models.DateTimeField(null=True, blank=True, help_text="Optional date from which the fee starts applying")
    end_date = models.DateTimeField(null=True, blank=True, help_text="Optional date after which the fee stops applying")
    is_active = models.BooleanField(default=True, help_text="Toggle to enable or disable this fee setup")

    def is_currently_active(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    def __str__(self):
        return f"{self.name} (Logged: Rs. {self.fee_logged_in}, Guest: Rs. {self.fee_guest})"
        
