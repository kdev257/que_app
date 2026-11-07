from django.shortcuts import render
from django.views.decorators.cache import cache_control

from accounts.views import customer_dashboard


def index(request):
    """Landing page = the service categories page (open to everyone).
    Login / guest login is asked only when a service is chosen."""
    return customer_dashboard(request)


@cache_control(no_cache=True)
def service_worker(request):
    """Served from the site root so it can show the offline page for every page."""
    return render(request, "pwa/sw.js", content_type="application/javascript")


def offline(request):
    return render(request, "pwa/offline.html")
