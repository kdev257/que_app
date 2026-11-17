from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('workspace/branch/<int:branch_id>/expenses/', views.expenses, name='list'),
    path('workspace/branch/<int:branch_id>/expenses/<int:expense_id>/delete/', views.expense_delete, name='delete'),
]
