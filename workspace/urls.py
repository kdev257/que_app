from django.urls import path

from . import views

app_name = 'workspace'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.business_signup, name='signup'),
    path('organization/', views.org_edit, name='org_edit'),
    path('branch/add/', views.branch_add, name='branch_add'),
    path('branch/<int:branch_id>/', views.branch_edit, name='branch_edit'),
    path('branch/<int:branch_id>/services/', views.services, name='services'),
    path('branch/<int:branch_id>/services/<int:service_id>/', views.service_edit, name='service_edit'),
    path('branch/<int:branch_id>/services/<int:service_id>/toggle/', views.service_toggle, name='service_toggle'),
    path('branch/<int:branch_id>/menu/', views.menu, name='menu'),
    path('branch/<int:branch_id>/menu/<int:item_id>/', views.menu_item_edit, name='menu_item_edit'),
    path('branch/<int:branch_id>/menu/<int:item_id>/toggle/', views.menu_item_toggle, name='menu_item_toggle'),
    path('branch/<int:branch_id>/reviews/', views.reviews, name='reviews'),
    path('branch/<int:branch_id>/qr/', views.qr_poster, name='qr_poster'),
    path('branch/<int:branch_id>/table-qr/', views.table_qr_sheet, name='table_qr_sheet'),
]
