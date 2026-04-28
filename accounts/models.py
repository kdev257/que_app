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
        
