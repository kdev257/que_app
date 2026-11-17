from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('workspace/branch/<int:branch_id>/stock/', views.stock, name='stock'),
    path('workspace/branch/<int:branch_id>/stock/item/<int:item_id>/', views.item_edit, name='item_edit'),
    path('workspace/branch/<int:branch_id>/suppliers/', views.suppliers, name='suppliers'),
    path('workspace/branch/<int:branch_id>/suppliers/<int:supplier_id>/', views.supplier_edit, name='supplier_edit'),
    path('workspace/branch/<int:branch_id>/purchases/', views.receipts, name='receipts'),
    path('workspace/branch/<int:branch_id>/purchases/new/', views.receipt_new, name='receipt_new'),
    path('workspace/branch/<int:branch_id>/purchases/<int:receipt_id>/', views.receipt_detail, name='receipt_detail'),
    path('workspace/branch/<int:branch_id>/closing-stock/', views.stock_counts, name='stock_counts'),
    path('workspace/branch/<int:branch_id>/closing-stock/new/', views.stock_count_new, name='stock_count_new'),
    path('workspace/branch/<int:branch_id>/closing-stock/<int:count_id>/', views.stock_count_detail, name='stock_count_detail'),
    path('workspace/branch/<int:branch_id>/closing-stock/<int:count_id>/review/', views.stock_count_review, name='stock_count_review'),
    # Staff screen (quantities only)
    path('branch/<int:branch_id>/stock-count/', views.staff_stock_count, name='staff_stock_count'),
]
