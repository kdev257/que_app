from django.urls import path

from . import views

app_name = 'privacy'

urlpatterns = [
    path('notice/', views.notice, name='notice'),
    path('consent/', views.consent, name='consent'),
    path('my-data/', views.my_data, name='my_data'),
    path('my-data/download/', views.export_data, name='export_data'),
    path('my-data/delete/', views.delete_account, name='delete_account'),
    path('grievance/', views.grievance, name='grievance'),
]
