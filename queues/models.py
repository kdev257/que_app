from django.utils import timezone
from django.db import models
from django.db.models import Max, Min
from login.models import User
from organization.models import Branch,Service
from accounts.models import Customer
# Create your models here.

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE)
    created_at = models.DateTimeField()

    def __str__(self):
        return f"Cart {self.id} - {self.user}"
    
    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)
    
    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart,on_delete=models.CASCADE,related_name="cart_items")
    service = models.ForeignKey(Service, on_delete=models.CASCADE,related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.service.name} in Cart {self.cart.id}"

    
class Queue(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE,default=1)
    date = models.DateField()
    last_token_number = models.IntegerField(default=0)
    current_serving_number = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # class Meta:
    #     unique_together = ('branch', 'date')    
    def __str__(self):
        return f"Queue for {self.branch.name} on {self.date}"    
    
class Token(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]    
    
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,default=1)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    token_number = models.IntegerField(default=0)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES, default="waiting"    )
    created_at = models.DateTimeField()
    expected_start_time = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True) #Actual start time
    expected_end_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True) #Actual end time
    expected_waiting_time = models.IntegerField(null=True, blank=True)  # in minutes
    waiting_time = models.IntegerField(null=True, blank=True)  # actual WT in minutes
    expected_service_time = models.IntegerField(null=True, blank=True)  # in minutes
    actual_service_time = models.IntegerField(null=True, blank=True)  # in minutes
    is_occupied = models.BooleanField(default=False) # We ensure that a token is allocated only once. so by default it is false and when we allocate next based earliest expected end time  token to a customer we set it to true.

    def __str__(self):
        return f"Token {self.token_number} for {self.user.username} at {self.branch.name} - {self.expected_service_time} mins"
   
    
    def generate_token_number(self):
        today = timezone.localdate()  # safer than date.today() with timezones

        last_token = (
            Token.objects
            .filter(branch=self.branch, created_at__date=today)
            .aggregate(max_num=Max("token_number"))
        )

        last_number = last_token["max_num"] or 0
        return last_number + 1

    def save(self, *args, **kwargs):
        # Only generate on create
        if not self.pk and not self.token_number:
            self.token_number = self.generate_token_number()
            self.created_at = timezone.now()

        super().save(*args, **kwargs)


class TokenService(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name="history")
    service = models.ForeignKey('organization.Service', on_delete=models.CASCADE)
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE,default=1)
    status = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f" {self.token.token_number} - {self.service} {self.branch}"
    
    

