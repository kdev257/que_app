from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import cache_control

from accounts.views import customer_dashboard
from organization.models import Service_Category


def landing(request):
    """Public landing page: what QuickQueue is, its strengths, and links to the services pages."""
    return render(request, "landing.html", {
        "categories": Service_Category.objects.order_by("name"),
        "support_email": settings.SUPPORT_EMAIL,
    })


# Help pages: slug -> (template, title). Text lives in the templates (templates/help/).
HELP_PAGES = {
    "salon-setup": ("help/salon_setup.html", "Set up a salon or service business"),
    "restaurant-setup": ("help/restaurant_setup.html", "Set up a restaurant or dhaba"),
    "customers": ("help/customers.html", "Help for customers"),
}


def help_page(request, slug=""):
    """/help/ (list of guides) and /help/<slug>/ (one guide)."""
    if slug and slug not in HELP_PAGES:
        raise Http404("Help page not found")
    template, title = HELP_PAGES.get(slug, ("help/index.html", "Help"))
    return render(request, template, {
        "title": title, "slug": slug, "support_email": settings.SUPPORT_EMAIL,
        "guides": [(s, t) for s, (_, t) in HELP_PAGES.items()],
    })


def index(request):
    """Customer services page (/explore/): service categories, open to everyone.
    Login / guest login is asked only when a service is chosen."""
    return customer_dashboard(request)


@cache_control(no_cache=True)
def service_worker(request):
    """Served from the site root so it can show the offline page for every page."""
    return render(request, "pwa/sw.js", content_type="application/javascript")


def offline(request):
    return render(request, "pwa/offline.html")
