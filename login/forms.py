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

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = '__all__'

   
 

class Registrationform(UserCreationForm):
    class Meta:
        model = User        
        fields =['username','first_name','last_name','password1','password2','email']    

