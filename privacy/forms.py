from django import forms
from django.urls import reverse_lazy
from django.utils.text import format_lazy

from .models import DataRequest

NOTICE_LINK = format_lazy(
    'Please read our <a href="{}" target="_blank">Privacy Notice</a> first.', reverse_lazy("privacy:notice")
)


class ConsentFieldsMixin(forms.Form):
    """Adds the two required ticks used at sign-up, guest login and re-consent."""
    age_confirm = forms.BooleanField(
        required=True, label="I confirm I am 18 years of age or older.",
        error_messages={"required": "You must be 18 or older to use QuickQueue."},
    )
    accept_notice = forms.BooleanField(
        required=True,
        label="I agree to QuickQueue using my details for bookings, queue updates, payments and invoices, as explained in the Privacy Notice.",
        help_text=NOTICE_LINK,
        error_messages={"required": "Please give your consent to continue."},
    )


class ConsentForm(ConsentFieldsMixin):
    pass


class DataRequestForm(forms.ModelForm):
    """Rights request / grievance. Erasure and consent withdrawal use their own button."""
    class Meta:
        model = DataRequest
        fields = ["request_type", "details", "nominee_name", "nominee_contact"]
        labels = {"request_type": "What do you need?", "details": "Details"}
        widgets = {"details": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["request_type"].choices = [
            c for c in DataRequest.TYPE_CHOICES if c[0] not in ("erasure", "withdraw_consent")
        ]
        self.fields["nominee_name"].help_text = "Only for 'Nominate a person'."

    def clean(self):
        data = super().clean()
        if data.get("request_type") == "nominate" and not data.get("nominee_name"):
            self.add_error("nominee_name", "Please enter the nominee's name.")
        if data.get("request_type") in ("grievance", "correction") and not data.get("details"):
            self.add_error("details", "Please describe your request.")
        return data


class PublicGrievanceForm(forms.ModelForm):
    """For visitors who are not logged in."""
    class Meta:
        model = DataRequest
        fields = ["contact_name", "contact_email", "details"]
        labels = {"contact_name": "Your name", "contact_email": "Your email", "details": "Your complaint"}
        widgets = {"details": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = True
