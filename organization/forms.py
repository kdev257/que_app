from django import forms

from .gst import COMMON_SAC, fixed_rate_by_law
from .models import Branch


SAC_OTHER = "other"


class BranchGSTForm(forms.ModelForm):
    """The owner sets all GST details here (no QuickQueue admin needed)."""
    sac_choice = forms.ChoiceField(
        label="Type of service (SAC code)",
        choices=[("", "-- Choose --")] + [(code, f"{code} - {name}") for code, name in COMMON_SAC]
        + [(SAC_OTHER, "Other - I will type the SAC code")],
        help_text="Printed on every invoice. Salon, nails, spa, gym and restaurant rates are then set as per GST law.",
        required=False,
    )
    sac_other = forms.CharField(label="SAC code", required=False, max_length=8,
                                widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "e.g. 998311"}))

    class Meta:
        model = Branch
        fields = ["is_gst_registered", "gst_state_code", "gstin", "specified_premises", "gst_percentage",
                  "prices_include_gst", "invoice_prefix"]
        field_order = ["is_gst_registered", "gst_state_code", "gstin", "sac_choice", "sac_other", "specified_premises",
                       "gst_percentage", "prices_include_gst", "invoice_prefix"]
        labels = {
            "is_gst_registered": "Registered under GST",
            "gst_state_code": "State (as per GST registration)",
            "gstin": "GSTIN",
            "gst_percentage": "Total GST %",
            "invoice_prefix": "Invoice number prefix",
            "prices_include_gst": "My prices already include GST",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(self.Meta.field_order)
        category = self.instance.services_category if self.instance.services_category_id else None
        self.sac_code = self.instance.sac_code or (category.sac_code if category else "")
        known = {code for code, _ in COMMON_SAC}
        if self.sac_code in known:
            self.fields["sac_choice"].initial = self.sac_code
        elif self.sac_code:
            self.fields["sac_choice"].initial = SAC_OTHER
            self.fields["sac_other"].initial = self.sac_code
        self.fields["specified_premises"].label = "Restaurant in a hotel (specified premises) - 18% with input tax credit"
        if fixed_rate_by_law(self.sac_code, self.instance.specified_premises) is not None:
            field = self.fields["gst_percentage"]
            field.widget.attrs["readonly"] = True
            field.help_text = "Fixed by GST law for your type of business (set automatically)."

    def clean(self):
        cleaned = super().clean()
        choice = cleaned.get("sac_choice")
        if choice == SAC_OTHER:
            code = (cleaned.get("sac_other") or "").strip()
            if not (code.isdigit() and 4 <= len(code) <= 8):
                self.add_error("sac_other", "Enter the SAC code (4 to 8 digits).")
                return cleaned
            self.sac_code = code
        elif choice:
            self.sac_code = choice
        self.instance.sac_code = self.sac_code
        if self.sac_code != "996331":
            cleaned["specified_premises"] = False  # only restaurants can be in "specified premises"
        fixed = fixed_rate_by_law(self.sac_code, cleaned.get("specified_premises", False))
        if fixed is not None:
            rate, itc = fixed
            cleaned["gst_percentage"] = rate
            self.instance.itc_allowed = itc
        else:
            category = self.instance.services_category if self.instance.services_category_id else None
            self.instance.itc_allowed = category.itc_allowed if category else True
        return cleaned

    def clean_invoice_prefix(self):
        prefix = "".join(ch for ch in (self.cleaned_data.get("invoice_prefix") or "").upper() if ch.isalnum())[:4]
        if not prefix:
            return Branch.suggest_prefix(self.instance.name, self.instance.organization_id, self.instance.id)
        if Branch.objects.filter(organization_id=self.instance.organization_id, invoice_prefix=prefix).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Another branch of your business uses this prefix. Please choose another.")
        return prefix

    def clean_gstin(self):
        gstin = (self.cleaned_data.get("gstin") or "").strip().upper()
        return gstin or None

    def clean_gst_percentage(self):
        value = self.cleaned_data.get("gst_percentage")
        if value is not None and not (0 <= value <= 100):
            raise forms.ValidationError("GST % must be between 0 and 100.")
        return value
