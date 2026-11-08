"""
Icon + colour group for a service name. Picked once (when the name is created) and
stored on Service_Name, so pages only read stored values. Editable in Admin.
Icons are Bootstrap Icons class names.
"""

# group key -> label (colours are defined in CSS as .svc-<group>)
GROUPS = [
    ("hair", "Hair"),
    ("skin", "Skin & face"),
    ("nails", "Nails"),
    ("spa", "Spa & massage"),
    ("grooming", "Beard & grooming"),
    ("makeup", "Make-up"),
    ("health", "Health"),
    ("other", "Other"),
]

# First matching keyword wins: (keywords, icon, group)
RULES = [
    (("beard", "shave", "moustache", "mustache"), "bi-scissors", "grooming"),
    (("colour", "color", "highlight", "henna", "dye"), "bi-palette", "hair"),
    (("wash", "shampoo"), "bi-droplet-half", "hair"),
    (("hair", "cut", "trim", "blow", "straighten", "smooth", "keratin", "perm"), "bi-scissors", "hair"),
    (("spa", "massage", "aroma", "body", "foot", "reflex"), "bi-flower1", "spa"),
    (("facial", "face", "cleanup", "clean-up", "bleach", "skin", "glow"), "bi-stars", "skin"),
    (("thread", "brow", "wax", "lash", "eye"), "bi-eye", "skin"),
    (("nail", "manicure", "pedicure", "gel"), "bi-hand-index-thumb", "nails"),
    (("makeup", "make-up", "make up", "bridal", "party", "saree", "drape"), "bi-brush", "makeup"),
    (("dental", "teeth", "tooth"), "bi-emoji-smile", "health"),
    (("check", "consult", "doctor", "physio", "test", "blood", "health"), "bi-heart-pulse", "health"),
]

DEFAULT_ICON, DEFAULT_GROUP = "bi-bookmark-star", "other"


def guess_style(name):
    """Return (icon, group) for a service name, e.g. 'Hair Cut' -> ('bi-scissors', 'hair')."""
    text = (name or "").lower()
    for keywords, icon, group in RULES:
        if any(k in text for k in keywords):
            return icon, group
    return DEFAULT_ICON, DEFAULT_GROUP
