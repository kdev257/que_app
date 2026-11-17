"""
GST rules: state codes, GSTIN check and which tax applies (CGST+SGST, CGST+UTGST or IGST).

Place of supply (IGST Act 2017, section 12):
  * 12(4) "performed" rule - restaurant & catering, personal grooming (salon), fitness, beauty treatment,
    health services: place of supply = where the service is performed = the branch's state.
    So these are always intra-state (CGST + SGST/UTGST).
  * 12(2) "general" rule - other services:
      customer has GSTIN       -> customer's state (first 2 digits of GSTIN)
      customer address on record -> customer's state
      otherwise                -> supplier's state
Same state as supplier -> CGST + SGST (or CGST + UTGST in a UT without legislature); different -> IGST.
"""
import re
from decimal import Decimal, ROUND_HALF_UP

# (GST state code, name, is a Union Territory without its own legislature -> UTGST instead of SGST)
STATES = [
    ("01", "Jammu and Kashmir", False),
    ("02", "Himachal Pradesh", False),
    ("03", "Punjab", False),
    ("04", "Chandigarh", True),
    ("05", "Uttarakhand", False),
    ("06", "Haryana", False),
    ("07", "Delhi", False),
    ("08", "Rajasthan", False),
    ("09", "Uttar Pradesh", False),
    ("10", "Bihar", False),
    ("11", "Sikkim", False),
    ("12", "Arunachal Pradesh", False),
    ("13", "Nagaland", False),
    ("14", "Manipur", False),
    ("15", "Mizoram", False),
    ("16", "Tripura", False),
    ("17", "Meghalaya", False),
    ("18", "Assam", False),
    ("19", "West Bengal", False),
    ("20", "Jharkhand", False),
    ("21", "Odisha", False),
    ("22", "Chhattisgarh", False),
    ("23", "Madhya Pradesh", False),
    ("24", "Gujarat", False),
    ("26", "Dadra and Nagar Haveli and Daman and Diu", True),
    ("27", "Maharashtra", False),
    ("29", "Karnataka", False),
    ("30", "Goa", False),
    ("31", "Lakshadweep", True),
    ("32", "Kerala", False),
    ("33", "Tamil Nadu", False),
    ("34", "Puducherry", False),
    ("35", "Andaman and Nicobar Islands", True),
    ("36", "Telangana", False),
    ("37", "Andhra Pradesh", False),
    ("38", "Ladakh", True),
    ("97", "Other Territory", True),
]
STATE_NAMES = {code: name for code, name, _ in STATES}
UT_CODES = {code for code, _, is_ut in STATES if is_ut}
STATE_CHOICES = [(code, f"{name} ({code})") for code, name, _ in STATES]

# Old or short names people type
_ALIASES = {
    "j&k": "01", "jammu & kashmir": "01", "uttaranchal": "05", "new delhi": "07", "nct of delhi": "07",
    "up": "09", "orissa": "21", "mp": "23", "daman and diu": "26", "dadra and nagar haveli": "26",
    "pondicherry": "34", "andaman": "35", "a&n islands": "35", "ap": "37", "tamilnadu": "33", "wb": "19",
}

RULE_PERFORMED = "performed"
RULE_GENERAL = "general"
RULE_CHOICES = [
    (RULE_PERFORMED, "Where service is performed (salon, restaurant, gym, spa, clinic) - always CGST+SGST"),
    (RULE_GENERAL, "General rule (customer's state decides; may be IGST)"),
]
# Category names that follow the "where performed" rule (used to set existing categories)
PERFORMED_KEYWORDS = ("restaurant", "cafe", "catering", "dhaba", "food", "salon", "saloon", "barber", "beauty",
                      "parlour", "parlor", "spa", "grooming", "gym", "fitness", "yoga", "clinic", "hospital",
                      "health", "dental", "doctor")

TAX_INTRA = "intra"        # CGST + SGST
TAX_INTRA_UT = "intra_ut"  # CGST + UTGST
TAX_INTER = "inter"        # IGST
TAX_NONE = "none"          # not a GST invoice

_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
TWO_PLACES = Decimal("0.01")


def state_name(code):
    return STATE_NAMES.get(code or "", "")


def code_for_name(name):
    """Best-effort: '  maharashtra ' -> '27'. Returns '' if unknown."""
    key = " ".join((name or "").replace(".", " ").lower().split())
    if not key:
        return ""
    if key in _ALIASES:
        return _ALIASES[key]
    for code, state, _ in STATES:
        if state.lower() == key:
            return code
    return ""


def gstin_check_char(gstin14):
    total = 0
    for i, ch in enumerate(gstin14):
        product = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def gstin_error(gstin, state_code=""):
    """Return an error message, or '' if the GSTIN looks valid."""
    gstin = (gstin or "").strip().upper()
    if not _GSTIN_RE.match(gstin):
        return "Enter a valid 15-character GSTIN, e.g. 27ABCDE1234F1Z5."
    if gstin[:2] not in STATE_NAMES:
        return "The first 2 digits of the GSTIN are not a valid state code."
    if gstin_check_char(gstin[:14]) != gstin[14]:
        return "This GSTIN has a typing mistake (last character does not match). Please check it."
    if state_code and gstin[:2] != state_code:
        return f"This GSTIN belongs to {state_name(gstin[:2])} ({gstin[:2]}), but the state selected is {state_name(state_code)} ({state_code})."
    return ""


def place_of_supply(rule, supplier_code, customer_gstin="", customer_state_code=""):
    """Return the GST state code of the place of supply."""
    if rule == RULE_PERFORMED:
        return supplier_code
    customer_gstin = (customer_gstin or "").strip().upper()
    if len(customer_gstin) == 15 and customer_gstin[:2] in STATE_NAMES:
        return customer_gstin[:2]
    if customer_state_code in STATE_NAMES:
        return customer_state_code
    return supplier_code


def split_tax(gst_amount, supplier_code, pos_code):
    """Split a GST amount into CGST / SGST / UTGST / IGST. Returns a dict."""
    gst_amount = Decimal(gst_amount or 0)
    result = {"tax_type": TAX_INTRA, "cgst": Decimal("0.00"), "sgst": Decimal("0.00"),
              "utgst": Decimal("0.00"), "igst": Decimal("0.00")}
    if gst_amount <= 0:
        return result
    if supplier_code and pos_code and supplier_code != pos_code:
        result["tax_type"] = TAX_INTER
        result["igst"] = gst_amount
        return result
    half = (gst_amount / 2).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    result["cgst"] = half
    if supplier_code in UT_CODES:
        result["tax_type"] = TAX_INTRA_UT
        result["utgst"] = gst_amount - half
    else:
        result["sgst"] = gst_amount - half
    return result


# ---------------------------------------------------------------------------
# SAC codes and default GST rate per type of business
# (Notification 11/2017-CT(Rate), as amended by 15/2025-CT(Rate) w.e.f. 22-09-2025:
#  beauty & physical well-being services (group 99972) -> 5% without input tax credit;
#  restaurant services (996331) -> 5% without input tax credit, except "specified premises")
# ---------------------------------------------------------------------------
CATEGORY_DEFAULTS = [
    # (keywords, SAC code, GST %, input tax credit allowed)
    (("restaurant", "cafe", "dhaba", "food", "catering", "bakery"), "996331", "5.00", False),
    (("nail", "manicure", "pedicure"), "999722", "5.00", False),
    (("salon", "saloon", "barber", "hair"), "999721", "5.00", False),
    (("beauty", "parlour", "parlor", "cosmetic", "makeup"), "999722", "5.00", False),
    (("spa", "massage"), "999729", "5.00", False),
    (("gym", "fitness", "yoga", "health club"), "999723", "5.00", False),
]
COMMON_SAC = [
    ("999721", "Hairdressing and barbers services"),
    ("999722", "Cosmetic treatment, manicuring and pedicuring"),
    ("999723", "Physical well-being, health club & fitness centre"),
    ("999729", "Other beauty treatment services (spa, massage)"),
    ("996331", "Restaurant, cafe and eating places (incl. takeaway)"),
]


def category_defaults(name):
    """Return (sac_code, gst_rate, itc_allowed) suggested for a category name, or None."""
    key = (name or "").lower()
    for words, sac, rate, itc in CATEGORY_DEFAULTS:
        if any(word in key for word in words):
            return sac, rate, itc
    return None


def financial_year(day):
    """'26-27' for any date from 1 Apr 2026 to 31 Mar 2027."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


def fixed_rate_by_law(sac_code, specified_premises=False):
    """GST rate and input-tax-credit rule fixed by law, or None if the business can choose.
    - Beauty & physical well-being (SAC 99972x: salon, nails, spa, gym, yoga): 5% without ITC, mandatory
      (Notification 15/2025-CT(Rate), w.e.f. 22-09-2025; CBIC: no option of 18% with ITC).
    - Restaurant (SAC 996331): 5% without ITC; 18% with ITC only in "specified premises"
      (hotel with room tariff above Rs 7,500 per day, or hotel that opted in by declaration)."""
    sac = (sac_code or "").strip()
    if sac.startswith("99972"):
        return Decimal("5.00"), False
    if sac == "996331":
        return (Decimal("18.00"), True) if specified_premises else (Decimal("5.00"), False)
    return None
