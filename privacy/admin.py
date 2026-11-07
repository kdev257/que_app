from django.contrib import admin, messages
from django.utils import timezone

from .models import BreachIncident, ConsentRecord, DataRequest, ErasureNotice, PrivacyNotice, ProcessingLog
from .services import _send, dpo_contact_text, notify_breach


@admin.register(PrivacyNotice)
class PrivacyNoticeAdmin(admin.ModelAdmin):
    list_display = ("version", "title", "effective_from", "is_current")
    list_filter = ("is_current",)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("given_at", "user", "guest", "notice", "age_confirmed", "withdrawn_at")
    list_filter = ("notice", "age_confirmed")
    search_fields = ("user__username", "user__email", "guest__name", "guest__email")
    readonly_fields = [f.name for f in ConsentRecord._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(DataRequest)
class DataRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "request_type", "status", "contact_name", "created_at", "due_date", "overdue", "erase_after")
    list_filter = ("status", "request_type")
    search_fields = ("reference", "contact_name", "contact_email", "user__username", "guest__name")
    readonly_fields = ("reference", "created_at", "resolved_at")

    @admin.display(boolean=True, description="Overdue")
    def overdue(self, obj):
        return bool(obj.is_overdue)

    def save_model(self, request, obj, form, change):
        was_open = change and DataRequest.objects.filter(pk=obj.pk, status__in=["open", "in_progress"]).exists()
        if obj.handled_by is None:
            obj.handled_by = request.user
        super().save_model(request, obj, form, change)
        if was_open and obj.status in ("resolved", "rejected") and obj.response and obj.contact_email:
            _send(
                f"Update on your request {obj.reference} - QuickQueue",
                f"Hi {obj.contact_name},\n\nYour request ({obj.get_request_type_display()}) is now "
                f"{obj.get_status_display()}.\n\n{obj.response}\n\n"
                f"If you are not satisfied, you may complain to the Data Protection Board of India.\n"
                f"Contact: {dpo_contact_text()}\n",
                obj.contact_email,
            )


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "subject_user", "subject_guest", "object_type", "object_id", "ip_address")
    list_filter = ("action", "created_at")
    search_fields = ("subject_user__username", "subject_guest__name", "object_id", "note")
    readonly_fields = [f.name for f in ProcessingLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # logs are removed only by the retention command after the legal minimum


@admin.register(ErasureNotice)
class ErasureNoticeAdmin(admin.ModelAdmin):
    list_display = ("notified_at", "user", "guest", "erase_on_or_after", "cancelled")
    list_filter = ("cancelled",)


@admin.register(BreachIncident)
class BreachIncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "detected_at", "status", "board_report_due", "reported_to_board_at", "users_notified_at", "users_notified_count")
    list_filter = ("status",)
    filter_horizontal = ("affected_branches",)
    readonly_fields = ("board_report_due", "users_notified_at", "users_notified_count", "created_at")
    actions = ["send_user_notices", "mark_reported_to_board"]

    @admin.action(description="Email breach notice to affected users")
    def send_user_notices(self, request, queryset):
        for incident in queryset:
            sent = notify_breach(incident, request)
            self.message_user(request, f"'{incident.title}': notice emailed to {sent} users.", messages.SUCCESS)

    @admin.action(description="Mark as reported to Data Protection Board (now)")
    def mark_reported_to_board(self, request, queryset):
        queryset.filter(reported_to_board_at__isnull=True).update(reported_to_board_at=timezone.now())
        self.message_user(request, "Marked as reported. Add the Board reference number on each incident.")
