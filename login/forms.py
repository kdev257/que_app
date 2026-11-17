from django import forms
from django.contrib.auth.forms import UserCreationForm,PasswordChangeForm,PasswordResetForm,AuthenticationForm
from .models import Guest, User,UserProfile
from privacy.forms import ConsentFieldsMixin

class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'style': 'font-size: 25px; height: 50px; border: solid 2px;',
        })
        self.fields['password'].widget.attrs.update({
            'style': 'font-size: 25px; height: 50px;border: solid 2px;',
        })
        for field_name, field in self.fields.items():
            field.widget.attrs['style'] += ' font-size: 25px;'

# class UserProfileForm(forms.ModelForm):
#     class Meta:
#         model = UserProfile
#         fields = '__all__'


class UserProfileForm(forms.ModelForm):
    """Customer's own profile. Role, organization and branch are NOT editable here
    (they are set by QuickQueue admin or the Business Workspace), so nobody can make
    themselves a branch admin of someone else's branch."""
    class Meta:
        model = UserProfile
        fields = ['address', 'phone_no', 'state', 'city', 'pin_code', 'image', 'business_name', 'gstin']
        labels = {'business_name': 'Business name (for GST invoice, optional)', 'gstin': 'GSTIN (optional)'}

    def __init__(self, *args, **kwargs):
        kwargs.pop('user', None)
        super(UserProfileForm, self).__init__(*args, **kwargs)

    def clean_gstin(self):
        from organization.gst import gstin_error
        gstin = (self.cleaned_data.get('gstin') or '').strip().upper()
        if gstin:
            error = gstin_error(gstin)
            if error:
                raise forms.ValidationError(error)
        return gstin

class BranchChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, b):
        place = ", ".join(p for p in [b.locality, b.city] if p)
        return f"{b.name} - {place}" if place else b.name


class Registrationform(ConsentFieldsMixin, UserCreationForm):
    """Sign-up form. The two consent ticks (18+ and privacy notice) are required (DPDP Act).
    'Branch staff' picks a branch; the owner / branch admin must approve before staff access."""
    ACCOUNT_TYPES = [("customer", "Customer"), ("staff", "Branch staff (I work at a shop / restaurant)")]
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPES, initial="customer", widget=forms.RadioSelect,
                                     label="I am a", required=False)  # not sent = customer
    staff_branch = BranchChoiceField(queryset=None, required=False, label="Branch where you work",
                                     help_text="Your owner or branch admin will approve your request.")

    class Meta:
        model = User        
        fields =['username','first_name','last_name','password1','password2','email']    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from organization.models import Branch
        self.fields["staff_branch"].queryset = Branch.objects.filter(is_approved=True).order_by("name", "city")
        # Show "I am a" first
        order = ["account_type", "staff_branch"]
        self.order_fields(order + [f for f in self.fields if f not in order])

    def clean(self):
        cleaned = super().clean()
        cleaned["account_type"] = cleaned.get("account_type") or "customer"
        if cleaned["account_type"] == "staff" and not cleaned.get("staff_branch"):
            self.add_error("staff_branch", "Please choose the branch where you work.")
        return cleaned

class guest_login_form(ConsentFieldsMixin, forms.ModelForm):
    """Guest form. The two consent ticks (18+ and privacy notice) are required (DPDP Act)."""
    class Meta:
        model = Guest
        fields = ['name', 'email', 'phone_no', 'pin_code']