from django.urls import path
from . import views

app_name = 'restaurants'

urlpatterns = [
    # Search & Home
    path('search/', views.restaurant_search, name='restaurant_search'),
    
    # Customer Menu & Ordering
    path('menu/<int:branch_id>/', views.menu_view, name='menu_view'),
    path('add_to_order_cart/', views.add_to_order_cart, name='add_to_order_cart'),
    path('view_order_cart/', views.view_order_cart, name='view_order_cart'),
    path('checkout_order/', views.checkout_order, name='checkout_order'),
    
    # Real-time Order Status
    path('order_status/<int:order_id>/', views.order_status, name='order_status'),
    path('order_status_htmx/<int:order_id>/', views.order_status_htmx, name='order_status_htmx'),
    
    # Payments
    path('payment/<int:order_id>/', views.order_payment, name='order_payment'),
    path('payment/callback/', views.restaurant_payment_callback, name='restaurant_payment_callback'),
    
    # Kitchen & Table Dashboards
    path('kitchen/dashboard/<int:branch_id>/', views.kitchen_dashboard, name='kitchen_dashboard'),
    path('kitchen/accept_order/<int:order_id>/', views.accept_order, name='accept_order'),
    path('kitchen/reject_order/<int:order_id>/', views.reject_order, name='reject_order'),
    path('kitchen/update_order_status/<int:order_id>/<str:new_status>/', views.update_order_status, name='update_order_status'),
    path('kitchen/manage_tables/<int:branch_id>/', views.manage_tables, name='manage_tables'),
    path('kitchen/toggle_table/<int:table_id>/', views.toggle_table_status, name='toggle_table_status'),
    path('kitchen/toggle_delivery/<int:branch_id>/', views.toggle_delivery_status, name='toggle_delivery_status'),
    
    # Staff/Waiter Dashboard
    path('staff/dashboard/<int:branch_id>/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/mark_arrived/<int:order_id>/', views.staff_mark_arrived, name='staff_mark_arrived'),
    path('staff/mark_served/<int:order_id>/', views.staff_mark_served, name='staff_mark_served'),
    path('staff/mark_completed/<int:order_id>/', views.staff_mark_completed, name='staff_mark_completed'),
]
