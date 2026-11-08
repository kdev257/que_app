"""
Match customers to branches (used by the services list and restaurant search).

Search (when the customer types or picks a filter):
    name, city, locality, PIN code or landmark.

Default (no search) widens step by step until something is found:
    1. same PIN code
    2. nearby PIN codes (same first 3 digits = same postal sorting district in India)
    3. customer's city
    4. all branches in the category
"""
from django.db.models import Q

CRITERIA = (
    ("city", "City"),
    ("locality", "Area / locality"),
    ("landmark", "Landmark"),
    ("pin_code", "PIN code"),
)


def customer_location(request):
    """Return {'pin': '110001', 'city': 'Delhi'} for the logged-in user or session guest."""
    pin, city = "", ""
    if request.user.is_authenticated:
        profile = getattr(request.user, "user_profile", None) if hasattr(request.user, "user_profile") else None
        if profile:
            pin = (profile.pin_code or "").strip()
            city = profile.city.name if profile.city_id else ""
    else:
        guest_id = request.session.get("guest_id")
        if guest_id:
            from login.models import Guest
            guest = Guest.objects.filter(id=guest_id).first()
            if guest:
                pin = (guest.pin_code or "").strip()
    return {"pin": pin, "city": city}


def apply_search(qs, criteria="", selected_val="", q=""):
    """Filter by a chosen criteria value, or by free text across all fields."""
    selected_val, q = (selected_val or "").strip(), (q or "").strip()
    if selected_val:
        if criteria == "city":
            return qs.filter(city__iexact=selected_val)
        if criteria == "locality":
            return qs.filter(locality__iexact=selected_val)
        if criteria == "landmark":
            return qs.filter(landmarks__name__iexact=selected_val).distinct()
        if criteria == "pin_code":
            return qs.filter(pin_code__iexact=selected_val)
    if q:
        return qs.filter(
            Q(name__icontains=q) | Q(organization__name__icontains=q) | Q(city__icontains=q)
            | Q(locality__icontains=q) | Q(pin_code__icontains=q) | Q(landmarks__name__icontains=q)
        ).distinct()
    return None  # no search given


def match_nearby(qs, pin="", city=""):
    """Step-by-step widening. Returns (queryset, note) — note explains what is shown."""
    if pin:
        exact = qs.filter(pin_code=pin)
        if exact.exists():
            return exact, f"Showing branches in your PIN code {pin}."
        if len(pin) >= 3:
            nearby = qs.filter(pin_code__startswith=pin[:3])
            if nearby.exists():
                return nearby, f"No branches in {pin} yet. Showing nearby branches ({pin[:3]}xxx)."
    if city:
        in_city = qs.filter(city__iexact=city)
        if in_city.exists():
            return in_city, f"Showing branches in {city}."
    if pin or city:
        return qs, "No branches near you yet. Showing all branches."
    return qs, ""


def sort_branches(qs):
    """Open branches first, then best rated (stored rating), then name."""
    return qs.order_by("-is_open", "-rating_avg", "-rating_count", "name")


def filter_options(qs):
    """Values for the filter dropdowns (only from branches that can be shown)."""
    from restaurants.models import RestaurantLandmark

    def distinct_values(field):
        return (qs.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""})
                .values_list(field, flat=True).distinct().order_by(field))

    return {
        "cities": distinct_values("city"),
        "localities": distinct_values("locality"),
        "pin_codes": distinct_values("pin_code"),
        "landmarks": RestaurantLandmark.objects.filter(branch__in=qs).values_list("name", flat=True)
        .distinct().order_by("name"),
    }


def find_branches(request, qs):
    """
    One call for list pages. Reads ?criteria=&selected_val=&q= from the request.
    Returns (branches, note, is_search).
    """
    criteria = request.GET.get("criteria", "")
    selected_val = request.GET.get("selected_val", "")
    q = request.GET.get("q", "")
    searched = apply_search(qs, criteria, selected_val, q)
    if searched is not None:
        label = selected_val or q
        note = f'Results for "{label.strip()}".' if searched.exists() else f'No branches found for "{label.strip()}".'
        return sort_branches(searched), note, True
    loc = customer_location(request)
    branches, note = match_nearby(qs, loc["pin"], loc["city"])
    return sort_branches(branches), note, False
