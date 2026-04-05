from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from organization.models import Service_Category

# Create your views here.
@login_required
def customer_dashboard(request): 
    categories = Service_Category.objects.all()    
    context = {
        "categories": categories
    }

    return render(request, "accounts/customer_dashboard.html", context)
    