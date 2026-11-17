import datetime
from decimal import Decimal

from django import forms

from organization.gst import gstin_error

from .models import Expense, ExpenseCategory

NEW_CATEGORY = "__new__"
GST_CHOICES = [("0", "No GST / 0%"), ("5", "5%"), ("18", "18%"), ("40", "40%")]


class ExpenseForm(forms.ModelForm):
    category_choice = forms.ChoiceField(label="Category")
    new_category = forms.CharField(max_length=80, required=False, label="New category name",
                                   widget=forms.TextInput(attrs={"placeholder": "e.g. Generator diesel"}))
    gst_rate = forms.TypedChoiceField(choices=GST_CHOICES, coerce=Decimal, initial="0", label="GST on the bill")

    class Meta:
        model = Expense
        fields = ["date", "description", "paid_to", "paid_to_gstin", "amount_entered", "amount_includes_gst",
                  "gst_rate", "payment_mode", "bill_file"]
        labels = {"amount_entered": "Amount (₹)", "amount_includes_gst": "Amount includes GST",
                  "paid_to_gstin": "Paid to GSTIN (optional)", "bill_file": "Photo / PDF of bill (optional)"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_choice"].choices = (
            [("", "-- Select a category --")]
            + [(str(c.id), c.name) for c in ExpenseCategory.objects.all()]
            + [(NEW_CATEGORY, "+ Add a new category")]
        )
        self.order_fields(["date", "category_choice", "new_category", "description", "amount_entered",
                           "amount_includes_gst", "gst_rate", "paid_to", "paid_to_gstin", "payment_mode", "bill_file"])

    def clean_date(self):
        day = self.cleaned_data["date"]
        if day > datetime.date.today():
            raise forms.ValidationError("The date cannot be in the future.")
        return day

    def clean_amount_entered(self):
        amount = self.cleaned_data["amount_entered"]
        if amount <= 0:
            raise forms.ValidationError("Enter an amount more than 0.")
        return amount

    def clean_paid_to_gstin(self):
        gstin = (self.cleaned_data.get("paid_to_gstin") or "").strip().upper()
        if gstin:
            error = gstin_error(gstin)
            if error:
                raise forms.ValidationError(error)
        return gstin

    def clean_bill_file(self):
        f = self.cleaned_data.get("bill_file")
        if f and f.size > 8 * 1024 * 1024:
            raise forms.ValidationError("File is too large (max 8 MB).")
        if f and not f.name.lower().endswith((".jpg", ".jpeg", ".png", ".pdf", ".webp")):
            raise forms.ValidationError("Please upload a photo (JPG/PNG) or a PDF.")
        return f

    def clean(self):
        cleaned = super().clean()
        choice = cleaned.get("category_choice")
        if choice == NEW_CATEGORY:
            name = " ".join((cleaned.get("new_category") or "").split())
            if not name:
                self.add_error("new_category", "Please type the new category name.")
            else:
                cleaned["category"] = (ExpenseCategory.objects.filter(name__iexact=name).first()
                                       or ExpenseCategory(name=name))
        elif choice:
            cleaned["category"] = ExpenseCategory.objects.filter(pk=choice).first()
        return cleaned

    def get_category(self):
        category = self.cleaned_data["category"]
        if category.pk is None:  # new category: add it to the common list
            category.save()
        return category
