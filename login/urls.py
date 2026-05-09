# from django.urls import path
# from .views import *
#     # from django.conf import settings
#     # from django.conf.urls.static import static

# urlpatterns = [
#     path('user_login/', user_login, name='user_login'),
#     path('register/',registration, name='register'),
    
#     # path('login/', login, name='login'),    
#     path('logout/', logout_view, name='logout'),
# ]
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.registration, name='register'),
    path('user_login/', views.user_login, name='user_login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.user_profile, name='user_profile'),

    # Password Reset URLs
     path('password-reset/',
         auth_views.PasswordResetView.as_view(),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]
