from django import forms

from .models import Branch


class BranchGSTForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["is_gst_registered", "gstin", "gst_percentage", "prices_include_gst"]
        labels = {
            "is_gst_registered": "Registered under GST",
            "gstin": "GSTIN",
            "gst_percentage": "GST % (CGST + SGST)",
            "prices_include_gst": "My prices already include GST",
        }

    def clean_gstin(self):
        gstin = (self.cleaned_data.get("gstin") or "").strip().upper()
        return gstin or None

    def clean_gst_percentage(self):
        value = self.cleaned_data.get("gst_percentage")
        if value is not None and not (0 <= value <= 100):
            raise forms.ValidationError("GST % must be between 0 and 100.")
        return value
