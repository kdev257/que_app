from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .services import has_current_consent

EXEMPT_PREFIXES = ("/admin/", "/static/", "/media/", "/privacy/", "/log/logout", "/registration/", "/sw.js", "/offline/")


class ConsentRequiredMiddleware:
    """
    Logged-in users and guests must have given consent to the CURRENT privacy notice.
    If not (e.g. old account, or a new notice version), they are sent to the consent page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DPDP_ENFORCE_CONSENT", True) and not request.path.startswith(EXEMPT_PREFIXES):
            needs = False
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                needs = not user.is_superuser and not has_current_consent(user=user)
            elif request.session.get("guest_id"):
                from login.models import Guest
                guest = Guest.objects.filter(id=request.session["guest_id"]).first()
                needs = guest is not None and not has_current_consent(guest=guest)
            if needs:
                return redirect(f"{reverse('privacy:consent')}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
