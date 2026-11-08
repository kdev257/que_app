from django import forms
from django.contrib.auth.forms import UserCreationForm

from login.models import User
from organization.models import Branch, Organization, Service_Name
from privacy.forms import ConsentFieldsMixin


class BusinessSignupForm(ConsentFieldsMixin, UserCreationForm):
    """'List your business': owner login + organization in one step."""
    phone = forms.CharField(max_length=20, label="Your mobile number")
    org_name = forms.CharField(max_length=255, label="Business / organization name")
    org_email = forms.EmailField(label="Business email")
    org_phone = forms.CharField(max_length=20, label="Business phone")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "email"):
            self.fields[name].required = True
        # Show the consent ticks last
        order = ["org_name", "org_email", "org_phone", "first_name", "last_name", "email", "phone",
                 "username", "password1", "password2", "age_confirm", "accept_notice"]
        self.order_fields(order)


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "email", "phone"]
        labels = {"name": "Business / organization name"}


class BranchForm(forms.ModelForm):
    landmarks = forms.CharField(
        required=False, max_length=1000, label="Nearby landmarks",
        help_text="Separate with commas, e.g. Near City Mall, Opp. Metro Gate 2. Customers can search by these.",
        widget=forms.TextInput(attrs={"placeholder": "Near City Mall, Opp. Metro Gate 2"}),
    )

    class Meta:
        model = Branch
        fields = ["name", "services_category", "address", "locality", "city", "state", "pin_code",
                  "phone", "email", "number_of_employees", "opening_time", "closing_time", "offers_delivery",
                  "website_url", "instagram_url", "facebook_url", "google_maps_url", "whatsapp_number"]
        labels = {
            "name": "Branch name",
            "services_category": "Type of business",
            "number_of_employees": "Staff serving customers at the same time",
            "offers_delivery": "Offers home delivery (restaurants)",
            "website_url": "Website (optional)",
            "instagram_url": "Instagram page (optional)",
            "facebook_url": "Facebook page (optional)",
            "google_maps_url": "Google Maps / Google reviews link (optional)",
            "whatsapp_number": "WhatsApp number (optional)",
        }
        help_texts = {"number_of_employees": "Used to estimate waiting time."}
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "opening_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "closing_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("services_category", "pin_code", "phone", "city"):
            self.fields[name].required = True
        self.fields["number_of_employees"].min_value = 1
        if self.instance and self.instance.pk:
            self.initial["landmarks"] = ", ".join(self.instance.landmarks.values_list("name", flat=True))

    def clean_landmarks(self):
        seen, result = set(), []
        for part in (self.cleaned_data.get("landmarks") or "").split(","):
            name = " ".join(part.split())[:255]
            if name and name.lower() not in seen:
                seen.add(name.lower())
                result.append(name)
        return result

    def save_landmarks(self, branch):
        """Replace the branch's landmarks with the ones typed in the form."""
        from restaurants.models import RestaurantLandmark
        names = self.cleaned_data.get("landmarks") or []
        branch.landmarks.exclude(name__in=names).delete()
        existing = set(branch.landmarks.values_list("name", flat=True))
        RestaurantLandmark.objects.bulk_create(
            [RestaurantLandmark(branch=branch, name=n) for n in names if n not in existing]
        )


NEW_SERVICE = "new"


class ServiceForm(forms.Form):
    """Select a service name from the dropdown, or choose '+ Add a new service name' and type it."""
    service_choice = forms.ChoiceField(label="Service name")
    new_service_name = forms.CharField(max_length=255, required=False, label="New service name",
                                       widget=forms.TextInput(attrs={"placeholder": "e.g. Hair Spa"}))
    description = forms.CharField(required=False, max_length=500, label="Description (optional)",
                                  widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500,
                                                               "placeholder": "e.g. Includes wash and blow-dry"}))
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, label="Price (₹)")
    average_time_minutes = forms.IntegerField(min_value=1, max_value=600, label="Average time (minutes)")
    is_active = forms.BooleanField(required=False, initial=True, label="Active (customers can book)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        names = Service_Name.objects.order_by("name").values_list("id", "name")
        self.fields["service_choice"].choices = (
            [("", "-- Select a service --")]
            + [(str(pk), name) for pk, name in names]
            + [(NEW_SERVICE, "+ Add a new service name")]
        )

    def clean(self):
        data = super().clean()
        choice = data.get("service_choice")
        if choice == NEW_SERVICE:
            name = " ".join((data.get("new_service_name") or "").split())
            if not name:
                self.add_error("new_service_name", "Please type the new service name.")
            data["service_name"] = name
        elif choice:
            data["service_name"] = Service_Name.objects.get(pk=int(choice)).name
        return data


class MenuItemForm(forms.Form):
    category_name = forms.CharField(max_length=100, label="Menu section",
                                    widget=forms.TextInput(attrs={"list": "menu-categories", "autocomplete": "off",
                                                                  "placeholder": "e.g. Starters"}))
    item_name = forms.CharField(max_length=255, label="Item name",
                                widget=forms.TextInput(attrs={"list": "menu-items", "autocomplete": "off",
                                                              "placeholder": "e.g. Paneer Tikka"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, label="Price (₹)")
    preparation_time_minutes = forms.IntegerField(min_value=1, max_value=240, initial=15, label="Preparation time (minutes)")
    is_veg = forms.BooleanField(required=False, initial=True, label="Vegetarian")
    is_available = forms.BooleanField(required=False, initial=True, label="Available")

    def clean_category_name(self):
        return " ".join(self.cleaned_data["category_name"].split())

    def clean_item_name(self):
        return " ".join(self.cleaned_data["item_name"].split())
