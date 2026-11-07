"""
Data protection (India DPDP Act 2023 / DPDP Rules 2025) records.
Everything is stored in the database so it can be shown, audited and proved later.
"""
import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class PrivacyNotice(models.Model):
    """The privacy notice shown to users. Admin can publish a new version;
    users are then asked to consent again."""
    version = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200, default="Privacy Notice")
    body = models.TextField(help_text="Plain text. Blank lines start a new paragraph. Lines starting with '- ' become bullet points.")
    effective_from = models.DateTimeField(default=timezone.now)
    is_current = models.BooleanField(default=False, help_text="Only one notice should be current.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.title} v{self.version}{' (current)' if self.is_current else ''}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            PrivacyNotice.objects.exclude(pk=self.pk).update(is_current=False)

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).order_by("-effective_from").first()


class ConsentRecord(models.Model):
    PURPOSE_CHOICES = [
        ("service", "Bookings, queue updates, payments and invoices"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="consents")
    guest = models.ForeignKey("login.Guest", on_delete=models.CASCADE, null=True, blank=True, related_name="consents")
    notice = models.ForeignKey(PrivacyNotice, on_delete=models.PROTECT, related_name="consents")
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default="service")
    age_confirmed = models.BooleanField(default=False, help_text="User confirmed they are 18 or older")
    given_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-given_at"]

    def __str__(self):
        who = self.user or self.guest
        state = "withdrawn" if self.withdrawn_at else "active"
        return f"Consent v{self.notice.version} by {who} ({state})"

    @property
    def is_active(self):
        return self.withdrawn_at is None


class DataRequest(models.Model):
    """Data principal rights requests and grievances."""
    TYPE_CHOICES = [
        ("access", "Get a summary of my data"),
        ("correction", "Correct / update my data"),
        ("erasure", "Delete my data"),
        ("withdraw_consent", "Withdraw consent"),
        ("nominate", "Nominate a person (in case of death or incapacity)"),
        ("grievance", "Complaint / grievance"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In progress"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected"),
    ]
    reference = models.CharField(max_length=30, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="data_requests")
    guest = models.ForeignKey("login.Guest", on_delete=models.SET_NULL, null=True, blank=True, related_name="data_requests")
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    request_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    details = models.TextField(blank=True)
    nominee_name = models.CharField(max_length=150, blank=True)
    nominee_contact = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    response = models.TextField(blank=True, help_text="Reply to the user (emailed when resolved/rejected)")
    created_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="handled_data_requests")
    # Erasure is carried out by the retention command on/after this date
    erase_after = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} - {self.get_request_type_display()} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.due_date:
            days = getattr(settings, "DPDP_RESPONSE_DAYS", 90)
            self.due_date = (self.created_at or timezone.now()).date() + datetime.timedelta(days=days)
        if self.status in ("resolved", "rejected") and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f"DPR-{self.created_at:%Y%m%d}-{self.pk:05d}"
            super().save(update_fields=["reference"])

    @property
    def is_overdue(self):
        return self.status in ("open", "in_progress") and self.due_date and self.due_date < timezone.now().date()


class ProcessingLog(models.Model):
    """Log of important processing of personal data. Kept for at least 1 year (DPDP Rule 8(3))."""
    ACTION_CHOICES = [
        ("register", "Account created"),
        ("guest_login", "Guest details collected"),
        ("login", "Login"),
        ("consent_given", "Consent given"),
        ("consent_withdrawn", "Consent withdrawn"),
        ("booking", "Booking / order created"),
        ("invoice_created", "Invoice created"),
        ("invoice_viewed", "Invoice viewed"),
        ("profile_updated", "Profile updated"),
        ("data_exported", "Data downloaded by user"),
        ("request_created", "Rights request / grievance created"),
        ("erasure_scheduled", "Erasure scheduled"),
        ("erasure_notice", "Pre-erasure notice sent"),
        ("anonymised", "Personal data anonymised"),
        ("breach_notice", "Breach notice sent"),
    ]
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    subject_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    subject_guest = models.ForeignKey("login.Guest", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    object_type = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.get_action_display()}"


class ErasureNotice(models.Model):
    """Records the 'your data will be deleted' email sent at least 48 hours before anonymising."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    guest = models.ForeignKey("login.Guest", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    notified_at = models.DateTimeField(default=timezone.now)
    erase_on_or_after = models.DateTimeField()
    cancelled = models.BooleanField(default=False, help_text="Set if the user became active again")

    def __str__(self):
        return f"Erasure notice to {self.user or self.guest} on {self.notified_at:%Y-%m-%d}"


class BreachIncident(models.Model):
    """Personal data breach register (DPDP Rule 7)."""
    STATUS_CHOICES = [
        ("open", "Open"),
        ("contained", "Contained"),
        ("closed", "Closed"),
    ]
    title = models.CharField(max_length=200)
    detected_at = models.DateTimeField(default=timezone.now)
    nature_and_extent = models.TextField(help_text="What happened and what data was affected")
    likely_impact = models.TextField(blank=True, help_text="Likely consequences for users")
    mitigation = models.TextField(blank=True, help_text="Steps taken / being taken")
    user_safety_steps = models.TextField(blank=True, help_text="What users should do to protect themselves")
    affected_branches = models.ManyToManyField("organization.Branch", blank=True, help_text="Users who booked at these branches will be notified")
    all_users_affected = models.BooleanField(default=False)
    board_report_due = models.DateTimeField(null=True, blank=True, help_text="Detailed report to the Data Protection Board due by")
    reported_to_board_at = models.DateTimeField(null=True, blank=True)
    board_reference = models.CharField(max_length=100, blank=True)
    users_notified_at = models.DateTimeField(null=True, blank=True)
    users_notified_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.title} ({self.detected_at:%Y-%m-%d})"

    def save(self, *args, **kwargs):
        if not self.board_report_due and self.detected_at:
            hours = getattr(settings, "DPDP_BREACH_REPORT_HOURS", 72)
            self.board_report_due = self.detected_at + datetime.timedelta(hours=hours)
        super().save(*args, **kwargs)
