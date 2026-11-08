"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


from login.views import user_profile

urlpatterns = [
    path('', views.index, name='index'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline, name='offline'),
    path('accounts/profile/', user_profile, name='user_profile'),        
    path('admin/', admin.site.urls),
    path('que/', include('queues.urls')),
    path('log/', include('login.urls')),
    path('org/', include('organization.urls')),
    path('acc/', include('accounts.urls')),
    path('restaurant/', include('restaurants.urls')),
    path('billing/', include('billing.urls')),
    path('privacy/', include('privacy.urls')),
    path('workspace/', include('workspace.urls')),
    path('reviews/', include('reviews.urls')),
    path('log/logout/', auth_views.LogoutView.as_view(next_page='/log/login/'), name='logout'),
    # Password reset email in HTML (must come before the include below)
    path('registration/password_reset/', auth_views.PasswordResetView.as_view(
        html_email_template_name='emails/password_reset.html'), name='password_reset'),
    path('registration/', include('django.contrib.auth.urls')),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)    
