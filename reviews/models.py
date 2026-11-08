from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Review(models.Model):
    """One rating per completed visit / order."""
    TAG_CHOICES = [
        ("on_time", "On time"),
        ("friendly", "Friendly staff"),
        ("clean", "Clean"),
        ("value", "Value for money"),
        ("quality", "Great quality"),
    ]
    token = models.OneToOneField("queues.Token", on_delete=models.CASCADE, related_name="review")
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")
    guest = models.ForeignKey("login.Guest", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated tag keys")
    comment = models.TextField(blank=True, max_length=1000)
    display_name = models.CharField(max_length=60, help_text="Shown publicly, e.g. 'Rahul S.'")
    is_hidden = models.BooleanField(default=False, help_text="Hidden by QuickQueue (abusive or fake)")
    reply = models.TextField(blank=True, max_length=1000)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ for {self.branch} by {self.display_name}"

    @property
    def tag_labels(self):
        labels = dict(self.TAG_CHOICES)
        return [labels[t] for t in self.tags.split(",") if t in labels]

    @property
    def stars(self):
        return "★" * self.rating + "☆" * (5 - self.rating)
