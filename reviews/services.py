import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count
from django.utils import timezone

EDIT_DAYS = 7
RATE_LINK_SALT = "reviews.rate_visit"
RATE_LINK_DAYS = 30


def rate_link(token):
    """Absolute, signed 'Rate your visit' link for emails. Works without login, only for this token."""
    from django.core import signing
    from django.urls import reverse
    from core.emails import site_link
    key = signing.dumps(token.id, salt=RATE_LINK_SALT)
    return site_link(reverse("reviews:rate_visit", args=[token.id])) + f"?k={key}"


def token_id_from_key(key):
    """Return the token id inside a valid, unexpired key, else None."""
    from django.core import signing
    try:
        return signing.loads(key, salt=RATE_LINK_SALT, max_age=RATE_LINK_DAYS * 24 * 3600)
    except signing.BadSignature:
        return None


def update_branch_rating(branch):
    """Store the branch's average rating and count in the database."""
    from .models import Review
    agg = Review.objects.filter(branch=branch, is_hidden=False).aggregate(avg=Avg("rating"), n=Count("id"))
    avg = Decimal(agg["avg"] or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    branch.rating_avg = avg
    branch.rating_count = agg["n"] or 0
    branch.save(update_fields=["rating_avg", "rating_count"])


def public_name(user=None, guest=None):
    """'Rahul S.' style name, for privacy."""
    if user is not None:
        first, last = (user.first_name or user.username).strip(), (user.last_name or "").strip()
    else:
        parts = (guest.name or "Guest").split()
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")
    return f"{first} {last[:1]}.".strip() if last else first


def can_edit(review):
    return review.created_at >= timezone.now() - datetime.timedelta(days=EDIT_DAYS)
