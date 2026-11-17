import datetime
from urllib.parse import quote_plus, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from organization.models import Service
from organization.permissions import can_manage_branch, is_restaurant_branch
from restaurants.models import MenuCategory, MenuItem
from reviews.models import Review
from workspace.views import ADMIN_ROLES, _branch_or_deny

from .forms import OfferForm, PhotoForm, SectionForm, SiteSettingsForm
from .images import shrink
from .models import MAX_PHOTOS, MAX_SECTIONS, BranchSite, SiteOffer, SitePhoto, SiteSection

IMAGE_SIZES = {"logo": 512, "banner": 1920}


# ---------------------------------------------------------------------------
# Public page: /b/<slug>/
# ---------------------------------------------------------------------------
def page(request, slug):
    site = get_object_or_404(
        BranchSite.objects.select_related("branch", "branch__services_category", "branch__organization"), slug=slug)
    branch = site.branch
    is_public = site.is_published and branch.is_approved
    can_edit = request.user.is_authenticated and can_manage_branch(request.user, branch.id, ADMIN_ROLES)
    if not is_public and not can_edit:
        raise Http404("Page not found")

    is_rest = is_restaurant_branch(branch)
    today = datetime.date.today()  # USE_TZ is off in this project
    services, menu = [], []
    if site.show_services:
        if is_rest:
            menu = (MenuCategory.objects.filter(branch=branch).select_related("name")
                    .prefetch_related(Prefetch("menu_items", to_attr="items",
                                               queryset=MenuItem.objects.filter(is_available=True).select_related("name")))
                    .order_by("name__name"))
            menu = [c for c in menu if c.items]
        else:
            services = Service.objects.filter(branch=branch, is_active=True).select_related("name").order_by("name__name")

    offers = []
    if site.show_offers:
        offers = (site.offers.filter(is_active=True)
                  .filter(Q(start_date__isnull=True) | Q(start_date__lte=today))
                  .filter(Q(valid_till__isnull=True) | Q(valid_till__gte=today)))

    reviews = []
    if site.show_reviews:
        reviews = Review.objects.filter(branch=branch, is_hidden=False).exclude(comment="")[:6]

    address = ", ".join(p for p in [branch.address, branch.locality, branch.city, branch.pin_code] if p)
    book_url = (reverse("restaurants:menu_view", args=[branch.id]) if is_rest
                else reverse("branch_services", args=[branch.id]))
    if not (request.user.is_authenticated or request.session.get("guest_id")):
        # Not logged in: Book now -> login / guest -> then straight to the booking page
        book_url = f"{reverse('login_choice')}?{urlencode({'next': book_url})}"

    return render(request, "branchsite/page.html", {
        "site": site, "branch": branch, "is_restaurant": is_rest,
        "is_preview": not is_public, "can_edit": can_edit,
        "services": services, "menu": menu, "offers": offers,
        "photos": site.photos.all() if site.show_gallery else [],
        "sections": site.sections.filter(is_active=True),
        "reviews": reviews,
        "address": address,
        "map_link": branch.google_maps_url or f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}",
        "map_embed": f"https://maps.google.com/maps?q={quote_plus(address)}&output=embed" if address else "",
        "book_url": book_url,
        "page_url": request.build_absolute_uri(),
    })


# ---------------------------------------------------------------------------
# Workspace: edit the website
# ---------------------------------------------------------------------------
def _replace_file(field_file, new_upload, max_px, old_name=""):
    """Save a smaller copy of the new photo, then delete the old file (if any)."""
    try:
        content = shrink(new_upload, max_px)
    except Exception:  # unusual image format: keep the original upload
        new_upload.seek(0)
        content = new_upload
    field_file.save(content.name, content, save=False)
    if old_name and old_name != field_file.name:
        field_file.storage.delete(old_name)


@login_required
def edit(request, branch_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    site = BranchSite.for_branch(branch)

    settings_form = SiteSettingsForm(instance=site)
    offer_form, photo_form, section_form = OfferForm(), PhotoForm(), SectionForm(initial={"sort_order": site.sections.count() + 1})

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "settings":
            old_files = {f: getattr(site, f).name for f in IMAGE_SIZES}
            settings_form = SiteSettingsForm(request.POST, request.FILES, instance=site)
            if settings_form.is_valid():
                site = settings_form.save(commit=False)
                for field, px in IMAGE_SIZES.items():
                    upload = request.FILES.get(field)
                    if upload:
                        _replace_file(getattr(site, field), upload, px, old_files[field])
                    elif not getattr(site, field) and old_files[field]:  # "Clear" ticked
                        site._meta.get_field(field).storage.delete(old_files[field])
                site.save()
                messages.success(request, "Website saved." + (" It is live now." if site.is_published and branch.is_approved else ""))
                return redirect("branchsite:edit", branch_id=branch.id)
        elif which == "offer":
            offer_form = OfferForm(request.POST)
            if offer_form.is_valid():
                offer = offer_form.save(commit=False)
                offer.site = site
                offer.save()
                messages.success(request, f"Offer '{offer.title}' added.")
                return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#offers")
        elif which == "photo":
            if site.photos.count() >= MAX_PHOTOS:
                messages.error(request, f"You can add up to {MAX_PHOTOS} photos. Please delete one first.")
                return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#photos")
            photo_form = PhotoForm(request.POST, request.FILES)
            if photo_form.is_valid():
                photo = photo_form.save(commit=False)
                photo.site = site
                _replace_file(photo.image, request.FILES["image"], 1600)
                photo.save()
                messages.success(request, "Photo added.")
                return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#photos")
        elif which == "section":
            if site.sections.count() >= MAX_SECTIONS:
                messages.error(request, f"You can add up to {MAX_SECTIONS} sections. Please delete one first.")
                return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#sections")
            section_form = SectionForm(request.POST, request.FILES)
            if section_form.is_valid():
                section = section_form.save(commit=False)
                section.site = site
                _save_section(section, request.FILES.get("image"))
                messages.success(request, f"Section '{section.title}' added.")
                return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#sections")

    return render(request, "branchsite/edit.html", {
        "branch": branch, "active": "website", "site": site,
        "settings_form": settings_form, "offer_form": offer_form, "photo_form": photo_form,
        "offers": site.offers.all(), "photos": site.photos.all(), "max_photos": MAX_PHOTOS,
        "section_form": section_form, "sections": site.sections.all(), "max_sections": MAX_SECTIONS,
        "is_restaurant": is_restaurant_branch(branch),
        "site_url": request.build_absolute_uri(reverse("branchsite:page", args=[site.slug])),
    })


@login_required
@require_POST
def offer_action(request, branch_id, offer_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    offer = get_object_or_404(SiteOffer, id=offer_id, site__branch=branch)
    if request.POST.get("action") == "delete":
        offer.delete()
        messages.success(request, "Offer deleted.")
    else:
        offer.is_active = not offer.is_active
        offer.save(update_fields=["is_active"])
        messages.success(request, "Offer shown on the website." if offer.is_active else "Offer hidden.")
    return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#offers")


@login_required
@require_POST
def photo_delete(request, branch_id, photo_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    photo = get_object_or_404(SitePhoto, id=photo_id, site__branch=branch)
    photo.image.delete(save=False)
    photo.delete()
    messages.success(request, "Photo deleted.")
    return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#photos")


# ---------------------------------------------------------------------------
# Own sections (title + text + optional photo)
# ---------------------------------------------------------------------------
def _save_section(section, upload, old_name=""):
    """Save the section; a new photo is made smaller, a removed or replaced photo is deleted."""
    if upload:
        _replace_file(section.image, upload, 1600, old_name)
    elif not section.image and old_name:  # "Clear" ticked
        section._meta.get_field("image").storage.delete(old_name)
    section.save()


@login_required
def section_edit(request, branch_id, section_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    section = get_object_or_404(SiteSection, id=section_id, site__branch=branch)
    old_name = section.image.name
    form = SectionForm(request.POST or None, request.FILES or None, instance=section)
    if request.method == "POST" and form.is_valid():
        _save_section(form.save(commit=False), request.FILES.get("image"), old_name)
        messages.success(request, "Section saved.")
        return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#sections")
    return render(request, "branchsite/section_edit.html", {
        "branch": branch, "active": "website", "form": form, "section": section,
    })


@login_required
@require_POST
def section_action(request, branch_id, section_id):
    branch, resp = _branch_or_deny(request, branch_id)
    if resp:
        return resp
    section = get_object_or_404(SiteSection, id=section_id, site__branch=branch)
    if request.POST.get("action") == "delete":
        if section.image:
            section.image.delete(save=False)
        section.delete()
        messages.success(request, "Section deleted.")
    else:
        section.is_active = not section.is_active
        section.save(update_fields=["is_active"])
        messages.success(request, "Section shown on the website." if section.is_active else "Section hidden.")
    return redirect(f"{reverse('branchsite:edit', args=[branch.id])}#sections")
