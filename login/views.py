from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetView, 
    PasswordResetDoneView, 
    PasswordResetConfirmView, 
    PasswordResetCompleteView
)
from django.urls import reverse_lazy
from .forms import Registrationform, CustomAuthenticationForm, UserProfileForm, guest_login_form
from .models import UserProfile

def registration(request):
    if request.method == 'POST':
        form = Registrationform(request.POST)        
        if form.is_valid():           
            form.save()
            messages.success(request, 'Your registration was successful. Please log in.')
            return redirect('user_login')
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
    else:
        form = Registrationform()
    return render(request, 'login/sign-up.html', {'form': form})

def user_login(request):    
    if request.method == 'POST':
        fm = CustomAuthenticationForm(request=request, data=request.POST)
        if fm.is_valid():            
            name = fm.cleaned_data['username']
            pw = fm.cleaned_data['password']
            user = authenticate(username=name, password=pw)                      
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Use try-except or a safer query to prevent crashes
                try:
                    user_profile = user.user_profile # Assumes related_name='user_profile'
                    if user_profile.role == 'customer':
                        return redirect('customer_dashboard')
                    elif user_profile.role == 'branch_admin':
                        return redirect('shop_dashboard', id=user_profile.branch.id)
                    elif user_profile.role == 'staff':
                        return redirect('restaurants:staff_dashboard', branch_id=user_profile.branch.id)
                    else:
                        return redirect('admin')
                except UserProfile.DoesNotExist:
                    return redirect('user_profile')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        fm = CustomAuthenticationForm()
    return render(request, 'login/login.html', {'form': fm}) 

@login_required 
def user_profile(request):
    # Get or Create profile to prevent RelatedObjectDoesNotExist crashes
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_login') # Or wherever appropriate
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    
    return render(request, 'login/profile.html', {'form': form})

def guest_login(request):
    if request.method == 'POST':
        form = guest_login_form(request.POST)
        if form.is_valid():
            guest = form.save()  # Save the guest to the database
            # Store guest ID in session so views can identify this guest
            request.session['guest_id'] = guest.id
            request.session.modified = True
            messages.success(request, f'Welcome, {guest.name}! You have logged in as a guest.')
            
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
                
            return redirect('customer_dashboard')
        else:
            messages.error(request, 'Guest login failed. Please correct the errors below.')
    else:
        form = guest_login_form()
    return render(request, 'login/guest_login.html', {'form': form})

def logout_view(request):
    logout(request)
    # Clear guest session on logout
    request.session.pop('guest_id', None)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('user_login')

# --- Password Reset Views (Class Based) ---

class MyPasswordResetView(PasswordResetView):
    template_name = 'login/password_reset_form.html'
    email_template_name = 'login/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')

class MyPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'login/password_reset_done.html'

class MyPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'login/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class MyPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'login/password_reset_complete.html'