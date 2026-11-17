from django.urls import path

from . import views

app_name = 'branchsite'

urlpatterns = [
    # Public page of a branch
    path('b/<slug:slug>/', views.page, name='page'),
    # Business Workspace: edit the page
    path('workspace/branch/<int:branch_id>/website/', views.edit, name='edit'),
    path('workspace/branch/<int:branch_id>/website/offer/<int:offer_id>/', views.offer_action, name='offer_action'),
    path('workspace/branch/<int:branch_id>/website/photo/<int:photo_id>/delete/', views.photo_delete, name='photo_delete'),
    path('workspace/branch/<int:branch_id>/website/section/<int:section_id>/', views.section_edit, name='section_edit'),
    path('workspace/branch/<int:branch_id>/website/section/<int:section_id>/action/', views.section_action, name='section_action'),
]
