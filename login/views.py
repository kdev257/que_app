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
from django.utils.http import url_has_allowed_host_and_scheme
from privacy.services import record_consent, log_processing


def _safe_next(request):
    """Return the ?next= URL only if it points to this site (blocks open redirects)."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def login_choice(request):
    """Shown when a visitor picks a service: log in, continue as guest, or register."""
    next_url = _safe_next(request) or ''
    if request.user.is_authenticated or request.session.get('guest_id'):
        return redirect(next_url or 'index')
    return render(request, 'login/login_choice.html', {'next': next_url})

def registration(request):
    if request.method == 'POST':
        form = Registrationform(request.POST)        
        if form.is_valid():           
            new_user = form.save()
            record_consent(request, user=new_user, age_confirmed=form.cleaned_data['age_confirm'])
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
                
                next_url = _safe_next(request)
                if next_url:
                    return redirect(next_url)
                
                # Use try-except or a safer query to prevent crashes
                try:
                    user_profile = user.user_profile # Assumes related_name='user_profile'
                    if user_profile.role == 'customer':
                        return redirect('customer_dashboard')
                    elif user_profile.role == 'org_admin':
                        return redirect('workspace:home')
                    elif user_profile.role == 'branch_admin':
                        if user_profile.branch_id:
                            return redirect('shop_dashboard', id=user_profile.branch_id)
                        return redirect('workspace:home')
                    elif user_profile.role == 'staff' and user_profile.branch_id:
                        return redirect('restaurants:staff_dashboard', branch_id=user_profile.branch_id)
                    elif user.is_staff:
                        return redirect('admin:index')
                    return redirect('index')
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
            log_processing('profile_updated', request, subject_user=request.user)
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
            log_processing('guest_login', request, subject_guest=guest)
            record_consent(request, guest=guest, age_confirmed=form.cleaned_data['age_confirm'])
            # Store guest ID in session so views can identify this guest
            request.session['guest_id'] = guest.id
            request.session.modified = True
            messages.success(request, f'Welcome, {guest.name}! You have logged in as a guest.')
            
            next_url = _safe_next(request)
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