"""Customers and guests are logged out after a few minutes without activity.
Business accounts (owner, branch admin, staff) and superusers are not affected
(they use the normal 4-hour session). Nobody is logged out while they have an
active booking or order, so they can keep watching their token / order status."""
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout

ACTIVE_TOKEN_STATUSES = ("waiting", "serving", "in_progress")


def _is_customer(user):
    if user.is_superuser or user.is_staff:
        return False
    from organization.permissions import BUSINESS_ROLES, get_user_profile
    profile = get_user_profile(user)
    return not (profile and profile.role in BUSINESS_ROLES)


def _has_active_booking(user=None, guest_id=None):
    from queues.models import Token
    tokens = Token.objects.filter(status__in=ACTIVE_TOKEN_STATUSES)
    return tokens.filter(user=user).exists() if user is not None else tokens.filter(guest_id=guest_id).exists()


class CustomerIdleLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        idle_limit = getattr(settings, "CUSTOMER_IDLE_LOGOUT_SECONDS", 300)
        user = request.user
        guest_id = request.session.get("guest_id")
        is_customer = user.is_authenticated and _is_customer(user)
        is_guest = not user.is_authenticated and bool(guest_id)

        if idle_limit and (is_customer or is_guest):
            now = time.time()
            last_seen = request.session.get("last_seen")
            if last_seen and now - last_seen > idle_limit and not _has_active_booking(
                    user=user if is_customer else None, guest_id=guest_id):
                if is_customer:
                    logout(request)          # also clears the session
                else:
                    request.session.flush()
                messages.info(request, f"You were logged out after {idle_limit // 60} minutes of no activity.")
            # Background refresh (HTMX polling) is not user activity
            elif not (request.method == "GET" and request.headers.get("HX-Request")):
                request.session["last_seen"] = now
        return self.get_response(request)
