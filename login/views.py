from django.shortcuts import render,redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.shortcuts import redirect
from .models import User,UserProfile
from .forms import CustomAuthenticationForm,UserProfileForm,Registrationform
from django.contrib.auth import login,authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from icecream import ic



# Create your views here.



def registration(request):
        if request.method =='POST':
            form = Registrationform(request.POST)        
            if form.is_valid():           
                form.save()
                messages.success(request,'Your registration was successful')
                return redirect('user_login')
            else:
                messages.error(request,'Your Registration Could not be Completed.Pls Contact Admin')
                
        else:
            form = Registrationform()
        return render(request,'login/sign-up.html',{'form':form})



def user_login(request):    
    if request.method=='POST':
        fm = CustomAuthenticationForm(request=request,data=request.POST)
        if fm.is_valid():            
            name = fm.cleaned_data['username']
            pw =fm.cleaned_data['password']
            user=authenticate(username=name,password=pw)                      
            if user is not None:
                login(request,user)
                messages.success(request,(f'Login Successful...Welcome {user}'))
                existing_profile = UserProfile.objects.filter(user=user).exists()
                if not existing_profile:
                    return redirect('user_profile')
                else:
                    user_profile = UserProfile.objects.get(user_id=user.id)
                    if user_profile.role == 'customer':
                        return redirect('customer_dashboard')
                    if user_profile.role == 'branch_admin':
                        branch_id = user_profile.branch.id
                        return redirect('shop_dashboard' , id=branch_id)
                    else:
                        return redirect('admin')            
                                
    else:
        fm=CustomAuthenticationForm()
    return render(request,'login/login.html',{'form':fm}) 

@login_required 
def user_profile(request):
    user = request.user 
    if user.is_authenticated:
        profile = request.user.user_profile
        if request.method == 'POST':
            # Pass user here for POST
            form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
            if form.is_valid():
                form.save()
                return redirect('user_login')
        else:
        # Pass user here for GET (This is where your current error is)
            form = UserProfileForm(instance=profile, user=request.user)
    else:
        messages.error(request,'You are not authorized to access this page')
    
    return render(request, 'login/profile.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('/')    