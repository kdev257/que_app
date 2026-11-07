import json

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ConsentForm, DataRequestForm, PublicGrievanceForm
from .models import ConsentRecord, DataRequest, PrivacyNotice
from .services import (
    _send, active_tokens_exist, dpo_contact_text, export_personal_data, has_current_consent,
    log_processing, record_consent, schedule_erasure,
)


def _subject(request):
    """Return (user, guest) for the current visitor; both None if anonymous."""
    if request.user.is_authenticated:
        return request.user, None
    guest_id = request.session.get("guest_id")
    if guest_id:
        from login.models import Guest
        return None, Guest.objects.filter(id=guest_id).first()
    return None, None


def _safe_next(request, default="index"):
    nxt = request.GET.get("next") or request.POST.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def _notice_blocks(notice):
    """Turn the stored notice text into paragraphs and bullet lists for the template."""
    blocks = []
    if not notice:
        return blocks
    for para in notice.body.replace("\r\n", "\n").split("\n\n"):
        lines = [ln.strip() for ln in para.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        if lines[0].startswith("## "):
            blocks.append({"type": "h", "text": lines[0][3:]})
            lines = lines[1:]
        bullets = [ln[2:] for ln in lines if ln.startswith("- ")]
        text = [ln for ln in lines if not ln.startswith("- ")]
        if text:
            blocks.append({"type": "p", "text": " ".join(text)})
        if bullets:
            blocks.append({"type": "ul", "items": bullets})
    return blocks


def notice(request):
    current = PrivacyNotice.current()
    return render(request, "privacy/notice.html", {"notice": current, "blocks": _notice_blocks(current)})


def consent(request):
    """Ask for consent to the current notice (old accounts / new notice version)."""
    user, guest = _subject(request)
    if user is None and guest is None:
        return redirect("index")
    if has_current_consent(user=user, guest=guest):
        return redirect(_safe_next(request))
    current = PrivacyNotice.current()
    if request.method == "POST":
        form = ConsentForm(request.POST)
        if form.is_valid():
            record_consent(request, user=user, guest=guest, age_confirmed=True)
            messages.success(request, "Thank you. Your consent is recorded.")
            return redirect(_safe_next(request))
    else:
        form = ConsentForm()
    return render(request, "privacy/consent.html", {
        "form": form, "notice": current, "blocks": _notice_blocks(current), "next": _safe_next(request, ""),
    })


def my_data(request):
    """'My Data & Privacy' page: see data, download it, make requests, delete account."""
    user, guest = _subject(request)
    if user is None and guest is None:
        return redirect("privacy:grievance")

    if request.method == "POST":
        form = DataRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.user, req.guest = user, guest
            req.contact_name = (user.get_full_name() or user.username) if user else guest.name
            req.contact_email = user.email if user else guest.email
            req.save()
            log_processing("request_created", request, subject_user=user, subject_guest=guest, obj=req)
            _send(
                f"We received your request {req.reference} - QuickQueue",
                f"Hi {req.contact_name},\n\nWe received your request: {req.get_request_type_display()}.\n"
                f"Reference: {req.reference}\nWe will reply by {req.due_date:%d %b %Y}.\n\n"
                f"Contact: {dpo_contact_text()}\n",
                req.contact_email,
            )
            messages.success(request, f"Request {req.reference} submitted. We will reply by {req.due_date:%d %b %Y}.")
            return redirect("privacy:my_data")
    else:
        form = DataRequestForm()

    data = export_personal_data(user=user, guest=guest)
    consents = ConsentRecord.objects.filter(user=user) if user else ConsentRecord.objects.filter(guest=guest)
    requests_qs = DataRequest.objects.filter(user=user) if user else DataRequest.objects.filter(guest=guest)
    return render(request, "privacy/my_data.html", {
        "data": data,
        "is_guest": guest is not None,
        "consents": consents.select_related("notice"),
        "data_requests": requests_qs,
        "form": form,
    })


def export_data(request):
    user, guest = _subject(request)
    if user is None and guest is None:
        return redirect("index")
    data = export_personal_data(user=user, guest=guest)
    log_processing("data_exported", request, subject_user=user, subject_guest=guest)
    response = HttpResponse(json.dumps(data, indent=2, default=str), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="my-quickqueue-data-{timezone.now():%Y%m%d}.json"'
    return response


def delete_account(request):
    """Withdraw consent and delete my data (confirmation page + POST)."""
    user, guest = _subject(request)
    if user is None and guest is None:
        return redirect("index")
    blocked = active_tokens_exist(user=user, guest=guest)
    if request.method == "POST":
        if blocked:
            messages.error(request, "Please finish or cancel your active bookings first.")
            return redirect("privacy:delete_account")
        if request.POST.get("confirm_text", "").strip().upper() != "DELETE":
            messages.error(request, "Please type DELETE to confirm.")
            return redirect("privacy:delete_account")
        req = schedule_erasure(request, user=user, guest=guest)
        if user is not None:
            logout(request)
        request.session.pop("guest_id", None)
        messages.success(
            request,
            f"Done. Your consent is withdrawn and your account is locked (ref {req.reference}). "
            f"Your data will be deleted on or after {req.erase_after:%d %b %Y}.",
        )
        return redirect("index")
    return render(request, "privacy/delete_account.html", {"blocked": blocked})


def grievance(request):
    """Public grievance form (for visitors without an account or session)."""
    user, guest = _subject(request)
    if user is not None or guest is not None:
        return redirect("privacy:my_data")
    if request.method == "POST":
        form = PublicGrievanceForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.request_type = "grievance"
            req.save()
            log_processing("request_created", request, obj=req)
            _send(
                f"We received your complaint {req.reference} - QuickQueue",
                f"Hi {req.contact_name},\n\nWe received your complaint. Reference: {req.reference}.\n"
                f"We will reply by {req.due_date:%d %b %Y}.\n\nContact: {dpo_contact_text()}\n",
                req.contact_email,
            )
            messages.success(request, f"Complaint {req.reference} submitted. We will reply by {req.due_date:%d %b %Y}.")
            return redirect("privacy:notice")
    else:
        form = PublicGrievanceForm()
    return render(request, "privacy/grievance.html", {"form": form})
