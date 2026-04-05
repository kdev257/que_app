from django.db import models
from django.core.exceptions import ValidationError
# Create your models here.



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
    opening_time = models.TimeField(blank=True, null=True,help_text="recommended to be filled accurately so that user can know when the branch opens while booking for service")
    closing_time = models.TimeField(blank=True, null=True,help_text="recommended to be filled accurately so that user can know when the branch closes while booking for service")

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.name} - {self.organization.name}"



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
    
    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

class Service(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE,related_name="service_branch")
    name = models.ForeignKey(Service_Name, on_delete=models.CASCADE,related_name="services")
    category = models.ForeignKey(Service_Category, on_delete=models.CASCADE,related_name="services_cat", blank=True, null=True)
    average_time_minutes = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    class Meta:
        ordering = ["name"]
        unique_together = ("branch", "name")

    def __str__(self):
        return f"{self.name} - {self.branch.name}"