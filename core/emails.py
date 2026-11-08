"""
One place to send all QuickQueue emails as HTML (with a plain-text copy for old mail apps).

    send_email("Token confirmed", "user@x.com", heading="Your token is ready",
               greeting="Hi Rahul,", paragraphs=["..."], rows=[("Token", "12")],
               button_text="Open QuickQueue", button_url=site_link("/"))
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def site_url():
    return getattr(settings, "SITE_URL", "").rstrip("/")


def site_link(path):
    """Absolute link for emails, e.g. site_link('/reviews/rate/5/')."""
    return f"{site_url()}{path}"


def from_address():
    addr = getattr(settings, "EMAIL_HOST_USER", None) or settings.DEFAULT_FROM_EMAIL
    return f"QuickQueue <{addr}>"


def _plain_text(context):
    """Plain-text copy built from the same parts as the HTML."""
    lines = [context.get("heading", ""), ""]
    if context.get("greeting"):
        lines += [context["greeting"], ""]
    for p in context.get("paragraphs") or []:
        lines += [strip_tags(str(p)), ""]
    for label, value in context.get("rows") or []:
        lines.append(f"{label}: {value}")
    if context.get("rows"):
        lines.append("")
    if context.get("extra_text"):
        lines += [context["extra_text"], ""]
    if context.get("button_url"):
        lines += [f"{context.get('button_text', 'Open')}: {context['button_url']}", ""]
    if context.get("note"):
        lines += [context["note"], ""]
    lines.append("QuickQueue - Skip the line. Book your slot.")
    return "\n".join(lines)


def build_email(subject, template="emails/base.html", **context):
    context.setdefault("subject", subject)
    context.setdefault("heading", subject)
    context.setdefault("preheader", context["heading"])
    context.setdefault("site_url", site_url())
    context.setdefault("logo_url", site_link("/static/pwa/icon-192.png") if site_url() else "")
    html = render_to_string(template, context)
    text = context.pop("text_body", None) or _plain_text(context)
    return html, text


def send_email(subject, to, template="emails/base.html", fail_silently=True, **context):
    """Send one HTML email. Returns True if sent. Never raises when fail_silently=True."""
    if not to:
        return False
    recipients = [to] if isinstance(to, str) else list(to)
    try:
        html, text = build_email(subject, template=template, **context)
        msg = EmailMultiAlternatives(subject=subject, body=text, from_email=from_address(), to=recipients)
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Email '%s' to %s failed", subject, recipients)
        if not fail_silently:
            raise
        return False


def send_text_as_html(subject, message, to, heading=None, **extra):
    """Turn an existing plain-text message into the branded HTML email (paragraphs kept)."""
    paragraphs = [p.strip() for p in message.strip().split("\n\n") if p.strip()]
    greeting = None
    if paragraphs and paragraphs[0].lower().startswith(("hi ", "hello ", "dear ")):
        greeting = paragraphs.pop(0)
    return send_email(subject, to, heading=heading or subject.split(" - ")[0], greeting=greeting,
                      paragraphs=paragraphs, text_body=message, **extra)
