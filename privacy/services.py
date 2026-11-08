"""Data protection helpers: consent, logging, export, erasure/anonymisation, breach notices."""
import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .models import ConsentRecord, DataRequest, PrivacyNotice, ProcessingLog

logger = logging.getLogger(__name__)

DELETED_GUEST_NAME = "Deleted guest"
DELETED_USER_PREFIX = "deleted_"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return ip or None


def retention_days():
    # DPDP Rule 8(3): keep data and logs at least 1 year from processing
    return max(365, int(getattr(settings, "DPDP_RETENTION_DAYS", 365)))


def log_processing(action, request=None, actor=None, subject_user=None, subject_guest=None, obj=None, note=""):
    """Write one processing log row. Never raises."""
    try:
        if actor is None and request is not None and request.user.is_authenticated:
            actor = request.user
        ProcessingLog.objects.create(
            action=action,
            actor=actor,
            subject_user=subject_user,
            subject_guest=subject_guest,
            object_type=obj.__class__.__name__ if obj is not None else "",
            object_id=str(obj.pk) if obj is not None else "",
            ip_address=client_ip(request),
            note=note[:255],
        )
    except Exception:
        logger.exception("Could not write processing log")


def _send(subject, message, email):
    """Send a privacy email as branded HTML (plain-text copy included). Never raises."""
    if not email:
        return False
    from core.emails import send_text_as_html
    return send_text_as_html(subject, message, email)


def dpo_contact_text():
    return (
        f"{getattr(settings, 'DPO_NAME', '') or 'Data Protection Officer'}, "
        f"{getattr(settings, 'DPO_EMAIL', '')} {getattr(settings, 'DPO_PHONE', '')}"
    ).strip()


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
def record_consent(request, user=None, guest=None, age_confirmed=True):
    notice = PrivacyNotice.current()
    if notice is None:
        return None
    consent = ConsentRecord.objects.create(
        user=user,
        guest=guest,
        notice=notice,
        age_confirmed=age_confirmed,
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:255],
    )
    log_processing("consent_given", request, subject_user=user, subject_guest=guest, obj=consent,
                   note=f"Notice v{notice.version}")
    return consent


def has_current_consent(user=None, guest=None):
    notice = PrivacyNotice.current()
    if notice is None:
        return True  # nothing to consent to yet
    qs = ConsentRecord.objects.filter(notice=notice, withdrawn_at__isnull=True)
    if user is not None:
        return qs.filter(user=user).exists()
    if guest is not None:
        return qs.filter(guest=guest).exists()
    return False


def withdraw_consent(request, user=None, guest=None):
    qs = ConsentRecord.objects.filter(withdrawn_at__isnull=True)
    qs = qs.filter(user=user) if user is not None else qs.filter(guest=guest)
    count = qs.update(withdrawn_at=timezone.now())
    log_processing("consent_withdrawn", request, subject_user=user, subject_guest=guest)
    return count


# ---------------------------------------------------------------------------
# Activity / export
# ---------------------------------------------------------------------------
def active_tokens_exist(user=None, guest=None):
    from queues.models import Token
    qs = Token.objects.filter(status__in=["waiting", "in_progress"])
    qs = qs.filter(user=user) if user is not None else qs.filter(guest=guest)
    return qs.exists()


def last_activity(user=None, guest=None):
    """Latest date/time we processed this person's data for a booking or login."""
    from queues.models import Token
    dates = []
    if user is not None:
        dates += [user.last_login, user.date_joined]
        latest = Token.objects.filter(user=user).aggregate(m=Max("created_at"))["m"]
    else:
        dates.append(getattr(guest, "created_at", None))
        latest = Token.objects.filter(guest=guest).aggregate(m=Max("created_at"))["m"]
    dates.append(latest)
    dates = [d for d in dates if d]
    return max(dates) if dates else timezone.now()


def export_personal_data(user=None, guest=None):
    """Everything we hold about this person, as a dict (for the 'Download my data' button)."""
    from billing.models import Invoice
    from queues.models import Token

    data = {"generated_at": timezone.now().isoformat(), "data_fiduciary": "QuickQueue"}
    if user is not None:
        profile = getattr(user, "user_profile", None) if hasattr(user, "user_profile") else None
        data["account"] = {
            "username": user.username, "first_name": user.first_name, "last_name": user.last_name,
            "email": user.email, "date_joined": str(user.date_joined), "last_login": str(user.last_login),
        }
        if profile:
            data["profile"] = {
                "phone_no": profile.phone_no, "address": profile.address, "pin_code": profile.pin_code,
                "city": str(profile.city or ""), "state": str(profile.state or ""), "role": profile.role,
                "has_profile_image": bool(profile.image),
            }
        tokens = Token.objects.filter(user=user)
        invoices = Invoice.objects.filter(customer_user=user)
        consents = ConsentRecord.objects.filter(user=user)
        requests = DataRequest.objects.filter(user=user)
    else:
        data["guest"] = {
            "name": guest.name, "email": guest.email, "phone_no": guest.phone_no, "pin_code": guest.pin_code,
        }
        tokens = Token.objects.filter(guest=guest)
        invoices = Invoice.objects.filter(customer_guest=guest)
        consents = ConsentRecord.objects.filter(guest=guest)
        requests = DataRequest.objects.filter(guest=guest)

    data["bookings"] = [
        {
            "token_number": t.token_number, "branch": t.branch.name, "date": str(t.token_date),
            "status": t.status, "amount": str(t.final_price), "payment_status": t.payment_status,
            "created_at": str(t.created_at),
            "delivery_address": getattr(getattr(t, "restaurant_order", None), "delivery_address", None)
            if hasattr(t, "restaurant_order") else None,
        }
        for t in tokens.select_related("branch")
    ]
    data["invoices"] = [
        {"invoice_number": i.invoice_number, "date": str(i.created_at), "branch": i.seller_name,
         "total": str(i.total_amount)}
        for i in invoices
    ]
    data["consents"] = [
        {"notice_version": c.notice.version, "given_at": str(c.given_at),
         "withdrawn_at": str(c.withdrawn_at) if c.withdrawn_at else None}
        for c in consents.select_related("notice")
    ]
    data["requests"] = [
        {"reference": r.reference, "type": r.get_request_type_display(), "status": r.get_status_display(),
         "created_at": str(r.created_at)}
        for r in requests
    ]
    from reviews.models import Review
    reviews_qs = Review.objects.filter(user=user) if user is not None else Review.objects.filter(guest=guest)
    data["reviews"] = [
        {"branch": r.branch.name, "rating": r.rating, "comment": r.comment, "shown_as": r.display_name,
         "date": str(r.created_at)}
        for r in reviews_qs.select_related("branch")
    ]
    data["shared_with"] = [
        "The branch / restaurant you book with",
        "Razorpay (online payments)",
        "Our email service provider (booking and invoice emails)",
    ]
    return data


# ---------------------------------------------------------------------------
# Erasure
# ---------------------------------------------------------------------------
def schedule_erasure(request, user=None, guest=None):
    """
    User asked to delete their data / withdrew consent.
    - Consent is withdrawn and the account is locked at once (data no longer used).
    - Data is anonymised by the daily retention command once the legal minimum
      (1 year from last processing, DPDP Rule 8(3)) has passed.
    """
    with transaction.atomic():
        withdraw_consent(request, user=user, guest=guest)
        erase_after = (last_activity(user=user, guest=guest) + datetime.timedelta(days=retention_days())).date()
        erase_after = max(erase_after, timezone.now().date())
        if user is not None:
            name, email = (user.get_full_name() or user.username), user.email
        else:
            name, email = guest.name, guest.email
        req = DataRequest.objects.create(
            user=user, guest=guest, contact_name=name, contact_email=email,
            request_type="erasure", status="in_progress",
            details="Requested from My Data page (consent withdrawn).",
            erase_after=erase_after,
        )
        if user is not None:
            user.is_active = False
            user.save(update_fields=["is_active"])
    log_processing("erasure_scheduled", request, subject_user=user, subject_guest=guest, obj=req,
                   note=f"Erase after {erase_after}")
    _send(
        "Your data deletion request - QuickQueue",
        f"Hi {name},\n\nWe received your request ({req.reference}).\n"
        f"Your consent is withdrawn and your account is locked, so your data is no longer used.\n"
        f"The law requires us to keep it securely for a minimum period; it will be deleted on or after {erase_after:%d %b %Y}.\n"
        f"Invoices are kept as required by tax law, without your email or phone number.\n\n"
        f"Questions: {dpo_contact_text()}\n",
        email,
    )
    return req


def _anonymise_reviews(user=None, guest=None):
    """Keep the star rating (no personal data) but remove the name and comment."""
    from reviews.models import Review
    qs = Review.objects.filter(user=user) if user is not None else Review.objects.filter(guest=guest)
    qs.update(display_name="Former customer", comment="")


def anonymise_user(user, request=None):
    from billing.models import Invoice
    from queues.models import Cart
    from restaurants.models import RestaurantOrder

    with transaction.atomic():
        profile = getattr(user, "user_profile", None) if hasattr(user, "user_profile") else None
        if profile:
            if profile.image:
                profile.image.delete(save=False)
            profile.address = ""
            profile.phone_no = None
            profile.pin_code = ""
            profile.state = None
            profile.city = None
            profile.image = None
            profile.save()
        RestaurantOrder.objects.filter(token__user=user).update(delivery_address="")
        Invoice.objects.filter(customer_user=user).update(customer_email="", customer_phone="")
        Cart.objects.filter(user=user).delete()
        _anonymise_reviews(user=user)
        DataRequest.objects.filter(user=user).update(contact_name="", contact_email="")
        ConsentRecord.objects.filter(user=user).update(ip_address=None, user_agent="")
        user.username = f"{DELETED_USER_PREFIX}{user.pk}"
        user.first_name = ""
        user.last_name = ""
        user.email = ""
        user.is_active = False
        user.set_unusable_password()
        user.save()
    log_processing("anonymised", request, subject_user=user)


def anonymise_guest(guest, request=None):
    from billing.models import Invoice
    from queues.models import Cart
    from restaurants.models import RestaurantOrder

    with transaction.atomic():
        RestaurantOrder.objects.filter(token__guest=guest).update(delivery_address="")
        Invoice.objects.filter(customer_guest=guest).update(customer_email="", customer_phone="")
        Cart.objects.filter(guest=guest).delete()
        _anonymise_reviews(guest=guest)
        DataRequest.objects.filter(guest=guest).update(contact_name="", contact_email="")
        ConsentRecord.objects.filter(guest=guest).update(ip_address=None, user_agent="")
        guest.name = DELETED_GUEST_NAME
        guest.email = ""
        guest.phone_no = ""
        guest.pin_code = ""
        guest.save()
    log_processing("anonymised", request, subject_guest=guest)


def is_anonymised(user=None, guest=None):
    if user is not None:
        return user.username.startswith(DELETED_USER_PREFIX)
    return guest.name == DELETED_GUEST_NAME


# ---------------------------------------------------------------------------
# Breach notification (DPDP Rule 7)
# ---------------------------------------------------------------------------
def breach_recipients(incident):
    """Set of (name, email) for users/guests affected by a breach."""
    from login.models import Guest, User
    from queues.models import Token

    recipients = {}
    if incident.all_users_affected:
        for u in User.objects.filter(is_active=True).exclude(email=""):
            recipients[u.email.lower()] = u.get_full_name() or u.username
        for g in Guest.objects.exclude(email=""):
            recipients.setdefault(g.email.lower(), g.name)
    else:
        tokens = Token.objects.filter(branch__in=incident.affected_branches.all()).select_related("user", "guest")
        for t in tokens:
            if t.user and t.user.email:
                recipients[t.user.email.lower()] = t.user.get_full_name() or t.user.username
            elif t.guest and t.guest.email:
                recipients.setdefault(t.guest.email.lower(), t.guest.name)
    return recipients


def notify_breach(incident, request=None):
    recipients = breach_recipients(incident)
    sent = 0
    for email, name in recipients.items():
        ok = _send(
            "Important: security incident affecting your data - QuickQueue",
            f"Hi {name},\n\n"
            f"We are informing you of a personal data breach.\n\n"
            f"What happened: {incident.nature_and_extent}\n"
            f"When: {incident.detected_at:%d %b %Y, %I:%M %p}\n"
            f"Possible impact on you: {incident.likely_impact or 'Being assessed'}\n"
            f"What we are doing: {incident.mitigation or 'Investigating and fixing the issue'}\n"
            f"What you can do: {incident.user_safety_steps or 'Be careful of unexpected calls, emails or messages asking for OTPs or payments.'}\n\n"
            f"Contact for questions: {dpo_contact_text()}\n",
            email,
        )
        sent += int(ok)
    incident.users_notified_at = timezone.now()
    incident.users_notified_count = sent
    incident.save(update_fields=["users_notified_at", "users_notified_count"])
    log_processing("breach_notice", request, obj=incident, note=f"{sent} users notified")
    return sent
