from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from organization.models import Service_Category
from django.utils import timezone
from .models import Promotion
from queues.views import customer_required, get_guest

# Create your views here.
@customer_required
def customer_dashboard(request):
    """Service categories page. Public: also used as the site landing page."""
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
        "guest": None if request.user.is_authenticated else get_guest(request),
    }
    

    return render(request, "accounts/customer_dashboard.html", context)
    