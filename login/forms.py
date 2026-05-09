from django import forms
from django.contrib.auth.forms import UserCreationForm,PasswordChangeForm,PasswordResetForm,AuthenticationForm
from .models import User,UserProfile

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
    class Meta:
        model = UserProfile
        fields = ['address', 'role', 'phone_no', 'organization', 'branch', 'state', 'city', 'pin_code', 'image']

    def __init__(self, *args, **kwargs):
        # We still pop user to avoid errors, but we don't delete fields here
        user = kwargs.pop('user', None) 
        super(UserProfileForm, self).__init__(*args, **kwargs)
        
        # Add an ID to the role field for the JavaScript to find easily
        self.fields['role'].widget.attrs.update({'id': 'id_role_select'})            

class Registrationform(UserCreationForm):
    class Meta:
        model = User        
        fields =['username','first_name','last_name','password1','password2','email']    

