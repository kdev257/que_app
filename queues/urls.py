from django.urls import path
from .views import *

urlpatterns = [
    path('services_category/', service_category, name='services_category'),
    path('services_list/<int:service_category_id>/', service_list, name='services_list'),
    path("create_token/<int:id>",create_token,name="create_token"),    
    path('branch_services/<int:branch_id>/', branch_services, name='branch_services'),
    path('add_to_cart/', add_to_cart, name='add_to_cart'),
    path('view_cart/<int:cart_id>/', view_cart, name='view_cart'),
    path('remove_cart_item/<int:item_id>/', remove_cart_item, name='remove_cart_item'),
    path('token_detail/<int:token_id>/', token_detail, name='token_detail'),
    path('shop_dashboard/<int:id>', shop_dashboard, name='shop_dashboard'),
    # path('update_token_status/<int:token_id>/', update_token_status, name='update_token_status'),
    path("start_service/<int:token_id>/", start_service, name="start_service"),
    path("end_service/<int:token_id>/", end_service, name="end_service"),
    path("delete_token/<int:token_id>/", delete_token, name="delete_token"),
]