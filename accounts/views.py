from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from organization.models import Service_Category
from django.utils import timezone
from .models import Promotion
from queues.views import login_or_guest_required, customer_required

# Create your views here.
@customer_required
@login_or_guest_required
def customer_dashboard(request):
    user_id = request.user.id 
    categories = Service_Category.objects.all()
    now = timezone.now()  
    
    # Query active hero promotions
    promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
        slot='hero'
    )
    
    # Query active popup promotions
    popup_promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
        slot='popup'
    )
        
    context = {
        "categories": categories,
        "user_id": user_id,
        "promotions": promotions,
        "popup_promotions": popup_promotions,
    }
    

    return render(request, "accounts/customer_dashboard.html", context)
    