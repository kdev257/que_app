from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class State(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}, {self.state.name}"

class User(AbstractUser):    
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.email})"    

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('superadmin', 'superadmin'),
        ('org_admin', 'org_admin'),
        ('branch_admin', 'brach_admin'),
        ('staff', 'staff'),
        ('supplier', 'supplier'),
        ('customer', 'customer'),
        ('service_provider', 'service_provider'),
        ('other', 'other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name='user_profile')    
    address = models.TextField()    
    role = models.CharField(max_length=30,choices=ROLE_CHOICES,default='customer')
    phone_no = models.CharField(max_length=20, blank=True, null=True)
    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE,null=True,
    blank=True,related_name="related_organization")
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE,null=True,
    blank=True,related_name="related_branch")
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True,related_name="user_state")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True,related_name="user_city"    )
    pin_code = models.CharField(max_length=10)
    image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
