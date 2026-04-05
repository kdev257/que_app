from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('user_login/', user_login, name='user_login'),
    path('register/',registration, name='register'),
    
    # path('login/', login, name='login'),    
    path('logout/', logout_view, name='logout'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)    