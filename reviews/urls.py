from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('rate/<int:token_id>/', views.rate_visit, name='rate_visit'),
    path('branch/<int:branch_id>/', views.branch_reviews, name='branch_reviews'),
]
