"""Branch offers that reduce the bill (set by the owner on the Website page).
The discount is worked out once when the order/booking is made and stored on the token;
the invoice then charges GST on the amount after discount."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

TWO_PLACES = Decimal("0.01")


def offer_discount(offer, amount):
    """Discount this offer gives on a bill amount (0 if the bill is below the minimum)."""
    amount = Decimal(amount or 0)
    if amount <= 0 or amount < (offer.min_bill_amount or 0):
        return Decimal("0.00")
    if offer.discount_type == "percent":
        discount = (amount * offer.discount_value / Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    elif offer.discount_type == "flat":
        discount = Decimal(offer.discount_value)
    else:
        return Decimal("0.00")
    if offer.max_discount:
        discount = min(discount, offer.max_discount)
    return min(discount, amount).quantize(TWO_PLACES)


def best_offer(branch, amount, day=None):
    """Return (offer, discount) for the best running offer of this branch, or (None, 0)."""
    from .models import SiteOffer
    day = day or datetime.date.today()
    offers = (SiteOffer.objects.filter(site__branch=branch, is_active=True, discount_type__in=("percent", "flat"))
              .filter(Q(start_date__isnull=True) | Q(start_date__lte=day))
              .filter(Q(valid_till__isnull=True) | Q(valid_till__gte=day)))
    best, best_amount = None, Decimal("0.00")
    for offer in offers:
        discount = offer_discount(offer, amount)
        if discount > best_amount:
            best, best_amount = offer, discount
    return best, best_amount
