"""
Daily data retention job (run once a day, e.g. Windows Task Scheduler or cron):

    python manage.py dpdp_retention            # do the work
    python manage.py dpdp_retention --dry-run  # only show what would happen

What it does:
1. Carries out scheduled erasure requests whose date has come.
2. Customers / guests inactive for DPDP_RETENTION_DAYS (min 365):
   - sends a "your data will be deleted" email at least 48 hours before,
   - then anonymises them (unless they became active again).
3. Deletes old abandoned carts.
4. Deletes processing logs older than DPDP_LOG_RETENTION_DAYS (min 365).
Invoices are kept (tax law) but without email/phone after anonymising.
"""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from login.models import Guest, User
from privacy.models import DataRequest, ErasureNotice, ProcessingLog
from privacy.services import (
    _send, active_tokens_exist, anonymise_guest, anonymise_user, dpo_contact_text,
    is_anonymised, last_activity, log_processing, retention_days,
)

NOTICE_HOURS = 48
STAFF_ROLES = ("superadmin", "org_admin", "branch_admin", "staff", "supplier", "service_provider")


def _is_customer(user):
    if user.is_superuser or user.is_staff:
        return False
    profile = getattr(user, "user_profile", None) if hasattr(user, "user_profile") else None
    return profile is None or profile.role not in STAFF_ROLES


class Command(BaseCommand):
    help = "Apply DPDP data retention: scheduled erasures, inactivity anonymisation, log cleanup."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report, change nothing.")

    def handle(self, *args, dry_run=False, **options):
        now = timezone.now()
        self.dry_run = dry_run
        self.stats = {"erased_requests": 0, "notices": 0, "anonymised": 0, "carts": 0, "logs": 0}

        self.process_erasure_requests(now)
        cutoff = now - datetime.timedelta(days=retention_days())
        for user in User.objects.filter(is_superuser=False):
            if _is_customer(user) and not is_anonymised(user=user):
                self.process_inactive(now, cutoff, user=user)
        for guest in Guest.objects.all():
            if not is_anonymised(guest=guest):
                self.process_inactive(now, cutoff, guest=guest)
        self.cleanup(now)

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Done: {self.stats}"))

    # 1. Erasure requests ---------------------------------------------------
    def process_erasure_requests(self, now):
        due = DataRequest.objects.filter(
            request_type="erasure", status__in=["open", "in_progress"], erase_after__lte=now.date()
        )
        for req in due:
            subject_user, subject_guest = req.user, req.guest
            if subject_user is None and subject_guest is None:
                continue
            if active_tokens_exist(user=subject_user, guest=subject_guest):
                continue  # wait until the booking is finished
            self.stats["erased_requests"] += 1
            if self.dry_run:
                continue
            email = req.contact_email
            if subject_user is not None:
                anonymise_user(subject_user)
            else:
                anonymise_guest(subject_guest)
            req.status = "resolved"
            req.response = "Your personal data has been deleted (invoices kept as required by tax law)."
            req.save()
            _send("Your data has been deleted - QuickQueue",
                  f"Your request {req.reference} is complete. Your personal data has been deleted.\n"
                  f"Questions: {dpo_contact_text()}\n", email)

    # 2. Inactivity ---------------------------------------------------------
    def process_inactive(self, now, cutoff, user=None, guest=None):
        notices = ErasureNotice.objects.filter(cancelled=False)
        notices = notices.filter(user=user) if user is not None else notices.filter(guest=guest)
        notice = notices.order_by("-notified_at").first()
        last = last_activity(user=user, guest=guest)

        if notice and last > notice.notified_at:
            # Became active again after the notice: cancel it
            if not self.dry_run:
                notice.cancelled = True
                notice.save(update_fields=["cancelled"])
            return

        if last > cutoff or active_tokens_exist(user=user, guest=guest):
            return

        if notice is None:
            self.stats["notices"] += 1
            if self.dry_run:
                return
            erase_at = now + datetime.timedelta(hours=NOTICE_HOURS)
            ErasureNotice.objects.create(user=user, guest=guest, erase_on_or_after=erase_at)
            name = (user.get_full_name() or user.username) if user is not None else guest.name
            email = user.email if user is not None else guest.email
            _send(
                "Your QuickQueue data will be deleted",
                f"Hi {name},\n\nYou have not used QuickQueue for a long time. As per our privacy notice, "
                f"your personal data will be deleted on or after {erase_at:%d %b %Y, %I:%M %p}.\n"
                f"To keep your account, just log in or make a booking before then.\n\n"
                f"Questions: {dpo_contact_text()}\n",
                email,
            )
            log_processing("erasure_notice", subject_user=user, subject_guest=guest)
            return

        if notice.erase_on_or_after <= now:
            self.stats["anonymised"] += 1
            if self.dry_run:
                return
            if user is not None:
                anonymise_user(user)
            else:
                anonymise_guest(guest)

    # 3 + 4. Cleanup ----------------------------------------------------------
    def cleanup(self, now):
        from queues.models import Cart
        old_carts = Cart.objects.filter(created_at__lt=now - datetime.timedelta(days=7))
        log_days = max(365, int(getattr(settings, "DPDP_LOG_RETENTION_DAYS", 365)))
        old_logs = ProcessingLog.objects.filter(created_at__lt=now - datetime.timedelta(days=log_days))
        self.stats["carts"] = old_carts.count()
        self.stats["logs"] = old_logs.count()
        if not self.dry_run:
            old_carts.delete()
            old_logs.delete()
