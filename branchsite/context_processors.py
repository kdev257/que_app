from urllib.parse import urlencode

from django.urls import reverse


def price_visibility(request):
    """Prices are shown only to visitors who logged in or continued as a guest
    (customers, guests, and of course business owners / staff)."""
    show = request.user.is_authenticated or bool(request.session.get("guest_id"))
    return {
        "show_prices": show,
        "price_login_url": "" if show else f"{reverse('login_choice')}?{urlencode({'next': request.get_full_path()})}",
    }
