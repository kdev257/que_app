from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('invoice/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('branch/<int:branch_id>/', views.branch_invoices, name='branch_invoices'),
    path('invoice/<int:invoice_id>/payment-mode/', views.set_payment_mode, name='set_payment_mode'),
    path('invoice/<int:invoice_id>/credit-note/', views.credit_note_create, name='credit_note_create'),
    path('credit-note/<int:credit_note_id>/', views.credit_note_detail, name='credit_note_detail'),
]
