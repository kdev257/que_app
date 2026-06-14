from django.db import models
from django.utils import timezone

class MenuCategoryName(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Menu Category Name"
        verbose_name_plural = "Menu Category Names"
        ordering = ['name']

    def __str__(self):
        return self.name


class MenuCategory(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='menu_categories')
    name = models.ForeignKey(MenuCategoryName, on_delete=models.CASCADE, related_name='menu_categories')
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Menu Categories"
        unique_together = ('branch', 'name')

    def __str__(self):
        return f"{self.name.name} - {self.branch.name}"


class GlobalMenuItem(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_veg = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Global Menu Item"
        verbose_name_plural = "Global Menu Items"
        ordering = ['name']

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='menu_items')
    name = models.ForeignKey(GlobalMenuItem, on_delete=models.CASCADE, related_name='branch_items')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_veg = models.BooleanField(default=True)
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    preparation_time_minutes = models.PositiveIntegerField(default=15, help_text="Preparation time in minutes")

    def save(self, *args, **kwargs):
        if self.name:
            self.is_veg = self.name.is_veg
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name.name} (₹{self.price})"


class Table(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='tables')
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    is_occupied = models.BooleanField(default=False)

    class Meta:
        unique_together = ('branch', 'table_number')

    def __str__(self):
        return f"Table {self.table_number} ({self.capacity} Pax) - {self.branch.name}"


class RestaurantOrder(models.Model):
    STATUS_CHOICES = [
        ('pending_confirmation', 'Pending Confirmation'),
        ('tentative', 'Tentative Confirmation'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('served', 'Served'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    ORDER_TYPES = [
        ('dine_in', 'Dine-In'),
        ('takeaway', 'Takeaway'),
        ('delivery', 'Deliver at Home'),
    ]

    token = models.OneToOneField('queues.Token', on_delete=models.CASCADE, related_name='restaurant_order')
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='restaurant_orders')
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_confirmation')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default='dine_in')
    delivery_address = models.TextField(null=True, blank=True, help_text="Delivery address for Deliver at Home orders")
    expected_delivery_time = models.DateTimeField(null=True, blank=True, help_text="Expected delivery time for home delivery orders")
    customer_arrived = models.BooleanField(default=False)
    minutes_until_arrival = models.PositiveIntegerField(null=True, blank=True, help_text="How many minutes until customer arrives at the restaurant")
    estimated_prep_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order for Token {self.token.token_number} - {self.branch.name} ({self.status})"

    @property
    def customer_name(self):
        if self.token.user:
            return self.token.user.first_name or self.token.user.username
        elif self.token.guest:
            return self.token.guest.name
        return "Unknown"

    @property
    def customer_phone(self):
        if self.token.user and hasattr(self.token.user, 'user_profile'):
            return self.token.user.user_profile.phone_no
        elif self.token.guest:
            return self.token.guest.phone_no
        return ""

    @property
    def minutes_until_arrival_dynamic(self):
        if self.token.expected_start_time:
            import datetime
            from django.utils import timezone
            if timezone.is_aware(self.token.expected_start_time):
                now = timezone.now()
            else:
                now = datetime.datetime.now()
            delta = self.token.expected_start_time - now
            minutes = int(delta.total_seconds() / 60)
            return max(0, minutes)
        return self.minutes_until_arrival or 0


class RestaurantOrderItem(models.Model):
    order = models.ForeignKey(RestaurantOrder, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Capture price at order time

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} in Order {self.order.id}"


class RestaurantLandmark(models.Model):
    branch = models.ForeignKey('organization.Branch', on_delete=models.CASCADE, related_name='landmarks')
    name = models.CharField(max_length=255, help_text="e.g. Near India Gate, Sector 62")

    def __str__(self):
        return f"{self.name} - {self.branch.name}"


class Highway(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., NH-44, Yamuna Expressway")
    start_point = models.CharField(max_length=100)
    end_point = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.start_point} to {self.end_point})"


class HighwayBranch(models.Model):
    DIRECTION_CHOICES = [
        ('UP', 'Towards End Point'),
        ('DOWN', 'Towards Start Point'),
        ('BOTH', 'Accessible from both sides'),
    ]

    branch = models.OneToOneField('organization.Branch', on_delete=models.CASCADE, related_name='highway_info')
    highway = models.ForeignKey(Highway, on_delete=models.CASCADE, related_name='branches')
    milestone_km = models.DecimalField(max_digits=6, decimal_places=2, help_text="KM marker along the highway")
    direction_of_travel = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='BOTH')
    is_exclusive = models.BooleanField(default=False)
    exclusivity_range_km = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Exclusivity range in km")
    segment = models.ForeignKey(
        'HighwaySegment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='branches',
        help_text="The segment/stretch of highway this branch is located in"
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.segment:
            if not self.branch or not self.branch.services_category or self.branch.services_category.name.lower() != 'restaurant':
                raise ValidationError({
                    'segment': "Highway segments can only be assigned to restaurant branches."
                })
            if self.segment.highway != self.highway:
                raise ValidationError({
                    'segment': f"The selected segment must belong to the highway '{self.highway}'."
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch.name} at KM {self.milestone_km} on {self.highway.name}"


class HighwaySegment(models.Model):
    highway = models.ForeignKey(Highway, on_delete=models.CASCADE, related_name='segments')
    start_place = models.CharField(max_length=100, help_text="e.g. Delhi")
    end_place = models.CharField(max_length=100, help_text="e.g. Agra")
    start_km = models.DecimalField(max_digits=6, decimal_places=2, help_text="Start KM milestone along the highway")
    end_km = models.DecimalField(max_digits=6, decimal_places=2, help_text="End KM milestone along the highway")

    class Meta:
        verbose_name = "Highway Segment"
        verbose_name_plural = "Highway Segments"
        unique_together = ('highway', 'start_place', 'end_place')

    def __str__(self):
        return f"{self.start_place} to {self.end_place} on {self.highway.name} (KM {self.start_km} -> {self.end_km})"

