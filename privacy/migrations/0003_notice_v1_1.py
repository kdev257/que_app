"""Privacy Notice v1.1: adds ratings & reviews, business GST details, branch websites and the
shared supplier list. Publishing a new version asks every customer/guest to accept it once."""
from django.db import migrations
from django.utils import timezone

ADDED_COLLECT = """- Your ratings and reviews of a visit (only if you give them)
- Your business name and GSTIN (only if you add them to get a GST invoice)"""

ADDED_SECTIONS = """## Ratings and reviews
If you rate a visit, your star rating, comment and first name (or the name you choose) are shown on that branch's page and website. The branch can reply. You can ask us to remove your review at any time from "My Data & Privacy".

## For businesses using QuickQueue
- Your branch website (name, photos, offers, timings, address, services and prices) is public once you publish it. Prices are shown only to visitors who log in or continue as a guest.
- Supplier business details you add (name, phone, WhatsApp, email, GSTIN, address, city and items they supply) are added to a shared supplier list. Other businesses of the same type in the same city can pick them. The contact person's name stays private to you.
- What you buy, from whom, and at what rate, your stock, expenses, invoices and reports are never shared with other businesses.
- Your GST details (GSTIN, state, SAC code) are printed on your customers' invoices."""


def publish_v1_1(apps, schema_editor):
    PrivacyNotice = apps.get_model("privacy", "PrivacyNotice")
    if PrivacyNotice.objects.filter(version="1.1").exists():
        return
    current = PrivacyNotice.objects.filter(is_current=True).order_by("-effective_from").first()
    if current is None:
        return
    body = current.body.replace("\r\n", "\n")
    marker = "- Technical details such as IP address and login time, for security"
    if marker in body:
        body = body.replace(marker, marker + "\n" + ADDED_COLLECT, 1)
    else:
        body = body + "\n\n## More data we collect\n" + ADDED_COLLECT
    body = body.replace("- The branch or restaurant you book with (your name, phone and booking details)",
                        "- The branch or restaurant you book with (your name, phone and booking details)\n"
                        "- Visitors to the branch page, for reviews you choose to post (see below)", 1)
    if "## Children" in body:
        body = body.replace("## Children", ADDED_SECTIONS + "\n\n## Children", 1)
    else:
        body = body + "\n\n" + ADDED_SECTIONS
    PrivacyNotice.objects.update(is_current=False)
    PrivacyNotice.objects.create(version="1.1", title=current.title, body=body, is_current=True,
                                 effective_from=timezone.now())


def undo(apps, schema_editor):
    PrivacyNotice = apps.get_model("privacy", "PrivacyNotice")
    PrivacyNotice.objects.filter(version="1.1").delete()
    previous = PrivacyNotice.objects.order_by("-effective_from").first()
    if previous:
        PrivacyNotice.objects.filter(pk=previous.pk).update(is_current=True)


class Migration(migrations.Migration):

    dependencies = [
        ('privacy', '0002_initial_notice'),
    ]

    operations = [
        migrations.RunPython(publish_v1_1, undo),
    ]
