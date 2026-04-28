from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from organization.models import Service_Category
from django.utils import timezone
from .models import Promotion

# Create your views here.
@login_required
def customer_dashboard(request):
    user_id = request.user.id 
    categories = Service_Category.objects.all()
    now = timezone.now()
    
        
    context = {
        "categories": categories,
        "user_id": user_id,        
    }
    

    return render(request, "accounts/customer_dashboard.html", context)
    