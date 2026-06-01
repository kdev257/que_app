from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.registration, name='register'),
    path('user_login/', views.user_login, name='user_login'),
    path('logout_view/', views.logout_view, name='logout_view'),
    path('profile/', views.user_profile, name='user_profile'),
    path('guest_login/', views.guest_login, name='guest_login'),


    # Password Reset URLs
#      path('password-reset/',
#          auth_views.PasswordResetView.as_view(),
#          name='password_reset'),

#     path('password-reset/done/',
#          auth_views.PasswordResetDoneView.as_view(),
#          name='password_reset_done'),

#     path('reset/<uidb64>/<token>/',
#          auth_views.PasswordResetConfirmView.as_view(),
#          name='password_reset_confirm'),

#     path('reset/done/',
#          auth_views.PasswordResetCompleteView.as_view(),
#          name='password_reset_complete'),
]
