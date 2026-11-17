from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('workspace/branch/<int:branch_id>/profit-loss/', views.profit_loss, name='profit_loss'),
    path('workspace/branch/<int:branch_id>/profit-loss/generate/', views.profit_loss_generate, name='profit_loss_generate'),
    path('workspace/branch/<int:branch_id>/profit-loss/<int:report_id>/', views.profit_loss_detail, name='profit_loss_detail'),
]
