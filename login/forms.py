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
        # 1. REMOVE 'user' from kwargs before calling super()
        user = kwargs.pop('user', None) 
        
        # 2. Now call super() - it won't see 'user' anymore and won't crash
        super(UserProfileForm, self).__init__(*args, **kwargs)

        # 3. Now use the user object for your logic
        user_role = None
        if user and hasattr(user, 'user_profile'):
            user_role = user.user_profile.role
        
        if user_role == 'customer':
            if 'organization' in self.fields:
                del self.fields['organization']
            if 'branch' in self.fields:
                del self.fields['branch']
            # Optional: Disable role changing for customers
            if 'role' in self.fields:
                self.fields['role'].disabled = True

class Registrationform(UserCreationForm):
    class Meta:
        model = User        
        fields =['username','first_name','last_name','password1','password2','email']    

