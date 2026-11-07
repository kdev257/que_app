from django.conf import settings


def data_protection(request):
    """Data protection contact details for every page (footer)."""
    return {
        "DPO_NAME": getattr(settings, "DPO_NAME", ""),
        "DPO_EMAIL": getattr(settings, "DPO_EMAIL", ""),
        "DPO_PHONE": getattr(settings, "DPO_PHONE", ""),
    }
