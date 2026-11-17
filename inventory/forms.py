from decimal import Decimal

from django import forms
from django.forms import formset_factory

from organization.gst import gstin_error

from .models import GST_RATE_CHOICES, Item, ItemCategory, ItemName, Receipt, Supplier, SupplierDirectory

NEW_ITEM = "__new__"
NEW_CATEGORY = "__newcat__"


NEW_SUPPLIER = "__new__"
DIRECTORY_FIELDS = ["name", "phone", "whatsapp", "email", "gstin", "address", "city", "items_supplied"]


class SupplierForm(forms.ModelForm):
    """Pick a supplier from the shared list (details are copied and can be edited), or add a new one.
    A new supplier's business details are added to the shared list for shops of the same type and city."""
    supplier_choice = forms.ChoiceField(label="Supplier", required=False)

    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "whatsapp", "email", "gstin", "address", "city", "items_supplied"]
        labels = {"gstin": "GSTIN (optional)", "items_supplied": "Items they supply",
                  "contact_person": "Contact person (only for you)"}

    def __init__(self, *args, organization=None, business_type="general", city="", **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.business_type = business_type
        self.directory_choices = SupplierDirectory.objects.none()
        if self.instance.pk:  # editing own copy: no dropdown
            self.fields.pop("supplier_choice")
            return
        allowed = [business_type, "general"] if business_type != "general" else ["beauty", "food", "general"]
        qs = SupplierDirectory.objects.filter(business_type__in=allowed)
        if city:
            qs = qs.filter(city__iexact=city.strip())
        already = Supplier.objects.filter(organization=organization, directory__isnull=False).values_list("directory_id", flat=True)
        self.directory_choices = qs.exclude(id__in=list(already))
        self.fields["supplier_choice"].choices = (
            [("", "-- Select a supplier --")]
            + [(str(d.id), f"{d.name}{' (' + d.items_supplied[:40] + ')' if d.items_supplied else ''}")
               for d in self.directory_choices]
            + [(NEW_SUPPLIER, "+ Add a new supplier")]
        )
        self.fields["supplier_choice"].initial = NEW_SUPPLIER if not self.directory_choices.exists() else ""
        self.fields["city"].initial = city
        self.order_fields(["supplier_choice"] + list(self.Meta.fields))

    def clean(self):
        cleaned = super().clean()
        choice = cleaned.get("supplier_choice")
        if "supplier_choice" in self.fields:
            if not choice:
                self.add_error("supplier_choice", "Select a supplier, or choose '+ Add a new supplier'.")
            elif choice != NEW_SUPPLIER:
                cleaned["directory"] = self.directory_choices.filter(id=choice).first()
                if cleaned["directory"] is None:
                    self.add_error("supplier_choice", "Please choose a supplier from the list.")
        return cleaned

    def save(self, commit=True):
        supplier = super().save(commit=False)
        directory = self.cleaned_data.get("directory")
        if directory is None and not supplier.pk:
            # New supplier: share only its business details (not the contact person)
            directory = SupplierDirectory.objects.filter(name__iexact=supplier.name, city__iexact=supplier.city).first()
            if directory is None:
                directory = SupplierDirectory.objects.create(
                    business_type=self.business_type, **{f: getattr(supplier, f) for f in DIRECTORY_FIELDS})
        if directory is not None:
            supplier.directory = directory
        if commit:
            supplier.save()
        return supplier

    def clean_gstin(self):
        gstin = (self.cleaned_data.get("gstin") or "").strip().upper()
        if gstin:
            error = gstin_error(gstin)
            if error:
                raise forms.ValidationError(error)
        return gstin

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Supplier.objects.filter(organization=self.organization, name__iexact=name).exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError("You already have a supplier with this name.")
        return name


class ItemForm(forms.ModelForm):
    """Select an item name from the dropdown, or choose '+ Add a new item' and type it
    (the new name is saved to the common list)."""
    item_choice = forms.ChoiceField(label="Item")
    new_item_name = forms.CharField(max_length=150, required=False, label="New item name",
                                    widget=forms.TextInput(attrs={"placeholder": "e.g. Gel polish - Red 15 ml"}))
    category_choice = forms.ChoiceField(label="Category", required=False)
    new_category = forms.CharField(max_length=60, required=False, label="New category name",
                                   widget=forms.TextInput(attrs={"placeholder": "e.g. Nail art supplies"}))

    class Meta:
        model = Item
        fields = ["unit", "min_stock", "hsn_code"]
        labels = {"min_stock": "Alert below (quantity)", "hsn_code": "HSN code (optional)"}

    def __init__(self, *args, organization=None, business_type="general", **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.business_type = business_type
        # Only names / categories for this type of business (plus common ones); 'general' sees all
        allowed = [business_type, "general"] if business_type != "general" else ["beauty", "food", "general"]
        self.order_fields(["item_choice", "new_item_name", "unit", "category_choice", "new_category",
                           "min_stock", "hsn_code"])
        categories = list(ItemCategory.objects.filter(business_type__in=allowed).values_list("name", flat=True))
        current = self.instance.category if self.instance.pk else ""
        if current and current not in categories:  # older free-text category stays selectable
            categories.append(current)
        self.fields["category_choice"].choices = (
            [("", "-- Select a category --")] + [(c, c) for c in sorted(categories)]
            + [(NEW_CATEGORY, "+ Add a new category")]
        )
        self.fields["category_choice"].initial = current
        # Hide names this business already has (except the one being edited)
        taken = Item.objects.filter(organization=organization).exclude(id=self.instance.id).values_list("name", flat=True)
        names = (ItemName.objects.filter(business_type__in=allowed).exclude(name__in=list(taken))
                 .values_list("id", "name"))
        self.allowed_types = allowed
        self.fields["item_choice"].choices = (
            [("", "-- Select an item --")] + [(str(pk), name) for pk, name in names]
            + [(NEW_ITEM, "+ Add a new item")]
        )
        if self.instance.pk:
            if self.instance.master_id:
                self.fields["item_choice"].initial = str(self.instance.master_id)
            else:
                self.fields["item_choice"].initial = NEW_ITEM
                self.fields["new_item_name"].initial = self.instance.name

    def clean(self):
        cleaned = super().clean()
        cat_choice = cleaned.get("category_choice") or ""
        if cat_choice == NEW_CATEGORY:
            cat = " ".join((cleaned.get("new_category") or "").split())
            if not cat:
                self.add_error("new_category", "Please type the new category name.")
            cleaned["category_name"] = cat
        else:
            cleaned["category_name"] = cat_choice
        choice = cleaned.get("item_choice")
        if choice == NEW_ITEM:
            name = " ".join((cleaned.get("new_item_name") or "").split())
            if not name:
                self.add_error("new_item_name", "Please type the new item name.")
                return cleaned
            master = ItemName.objects.filter(name__iexact=name).first()
        elif choice:
            master = ItemName.objects.filter(pk=choice, business_type__in=self.allowed_types).first()
            if master is None:
                self.add_error("item_choice", "Please choose an item from the list.")
                return cleaned
            name = master.name
        else:
            return cleaned
        if Item.objects.filter(organization=self.organization, name__iexact=name).exclude(id=self.instance.id).exists():
            self.add_error("item_choice", "This item is already in your list.")
            return cleaned
        cleaned["item_name"], cleaned["master"] = name, master
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        category = self.cleaned_data.get("category_name", "")
        if category:  # new category: add it to the common list
            existing = ItemCategory.objects.filter(name__iexact=category).first()
            category = existing.name if existing else ItemCategory.objects.create(
                name=category, business_type=self.business_type).name
        item.category = category
        master = self.cleaned_data.get("master")
        if master is None:  # new name: add it to the common list
            master = ItemName.objects.create(name=self.cleaned_data["item_name"], unit=item.unit, category=item.category,
                                             business_type=self.business_type)
        item.master, item.name = master, self.cleaned_data["item_name"]
        if commit:
            item.save()
        return item


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ["supplier", "bill_number", "bill_date", "rates_include_gst", "notes", "bill_file"]
        labels = {"bill_number": "Supplier bill no.", "rates_include_gst": "Rates on the bill include GST",
                  "bill_file": "Photo / PDF of bill (optional)"}
        widgets = {"bill_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.branch = branch
        self.fields["supplier"].queryset = Supplier.objects.filter(organization=branch.organization, is_active=True)

    def clean(self):
        cleaned = super().clean()
        supplier, number = cleaned.get("supplier"), (cleaned.get("bill_number") or "").strip()
        if supplier and number and Receipt.objects.filter(branch=self.branch, supplier=supplier,
                                                          bill_number__iexact=number).exists():
            raise forms.ValidationError("This bill from this supplier is already entered.")
        return cleaned

    def clean_bill_file(self):
        f = self.cleaned_data.get("bill_file")
        if f and f.size > 8 * 1024 * 1024:
            raise forms.ValidationError("File is too large (max 8 MB).")
        if f and not f.name.lower().endswith((".jpg", ".jpeg", ".png", ".pdf", ".webp")):
            raise forms.ValidationError("Please upload a photo (JPG/PNG) or a PDF.")
        return f


class ReceiptLineForm(forms.Form):
    item = forms.ModelChoiceField(queryset=Item.objects.none(), required=False)
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False)
    rate = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False,
                              label="Rate / unit")
    gst_rate = forms.TypedChoiceField(choices=[(str(v), l) for v, l in GST_RATE_CHOICES], coerce=Decimal,
                                      initial="18", label="GST")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.filter(organization=organization, is_active=True)

    def clean(self):
        cleaned = super().clean()
        filled = [cleaned.get("item"), cleaned.get("quantity"), cleaned.get("rate")]
        if any(v not in (None, "") for v in filled) and not all(v not in (None, "") for v in filled):
            raise forms.ValidationError("Fill item, quantity and rate (or leave the whole line empty).")
        return cleaned


ReceiptLineFormSet = formset_factory(ReceiptLineForm, extra=3)
