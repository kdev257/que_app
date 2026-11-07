from django.urls import path

from . import views

urlpatterns = [
    path('branch/<int:branch_id>/gst/', views.branch_gst_settings, name='branch_gst_settings'),
]
