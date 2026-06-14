import datetime
from django.utils import timezone
from django.db import models
from django.db.models import Max, Min
from login.models import User
from organization.models import Branch,Service
from accounts.models import Customer
# Create your models here.

def get_guest_model():
    """Lazy import to avoid circular imports."""
    from login.models import Guest
    return Guest

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    guest = models.ForeignKey('login.Guest', on_delete=models.CASCADE, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        owner = self.user.username if self.user else (self.guest.name if self.guest else 'Unknown')
        return f"Cart {self.id} - {owner}"
    
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
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, default=1)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    guest = models.ForeignKey('login.Guest', on_delete=models.CASCADE, null=True, blank=True)
    token_number = models.IntegerField(default=0)
    token_date = models.DateField(default=datetime.date.today)  # The date this token is for (not necessarily the created date)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting")
    created_at = models.DateTimeField(null=True, blank=True)
    expected_start_time = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)  # Actual start time
    expected_end_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)  # Actual end time
    expected_waiting_time = models.IntegerField(null=True, blank=True)  # in minutes
    waiting_time = models.IntegerField(null=True, blank=True)  # actual WT in minutes
    expected_service_time = models.IntegerField(null=True, blank=True)  # in minutes
    actual_service_time = models.IntegerField(null=True, blank=True)  # in minutes
    is_occupied = models.BooleanField(default=False)  # True once the slot is bridged to the next token
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(
        max_length=20, 
        choices=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
            ('pay_at_shop', 'Pay at Shop'),
            ('pay_at_home', 'Pay at Home'),
            ('refunded', 'Refunded'),
        ],
        default='unpaid'
    )
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        if self.user:
            name = self.user.username
        elif self.guest:
            name = self.guest.name
        else:
            name = 'Unknown'
        return f"Token {self.token_number} for {name} at {self.branch.name} - {self.expected_service_time} mins"
   
    @property
    def dynamic_waiting_time(self):
        from django.utils import timezone
        import datetime
        if self.status == 'waiting' and self.token_date == datetime.date.today() and self.expected_start_time:
            return max(0, int((self.expected_start_time - timezone.now()).total_seconds() / 60))
        return self.expected_waiting_time or 0
   
    
    
    def generate_token_number(self, target_date=None):
        """
        Generates the next sequential token number specifically for the target_date
        (whether it's today, tomorrow, or next week).
        """
        if target_date is None:
            target_date = self.token_date or datetime.date.today()
        # 1. Look for tokens specifically booked FOR the target_date
        tokens_for_day = Token.objects.filter(token_date=target_date)
        
        # 2. Find the highest token number assigned for that specific day
        last_token = tokens_for_day.order_by('-token_number').first()
        
        if last_token and last_token.token_number:
            # If tokens already exist for that day, increment the last one
            return last_token.token_number + 1
        else:
            # First token of that specific day always starts at 1
            return 1

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
    
    

