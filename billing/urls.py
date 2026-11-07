from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('invoice/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('branch/<int:branch_id>/', views.branch_invoices, name='branch_invoices'),
]
