from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from organization.models import Service, Service_Category, Branch
from accounts.models import Customer
from login.models import User
from .services import generate_token,calculate_real_waiting_time,calculate_service_time
from icecream import ic
from django.shortcuts import render,redirect
from organization.models import Service
from .models import Cart, CartItem,Token, TokenService 
from organization.models import Service, Branch
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count
from django.shortcuts import redirect
from django.db import transaction
from django.utils import timezone
import heapq
import math
from time import strftime
from django.db import transaction as db_transaction


# Create your views here.

def service_category(request):
    """Landing page for customers when they login, shows all the service categories available in the system"""
    services = Service_Category.objects.all()
    return render(request, "queues/services.html", {"services": services})

def service_list(request, service_category_id):
    """This view shows all the services available in the system for a particular category, it also filters the services based on the user's location to show only those services which are available in the user's area. It uses the pin code of the user and the pin code of the branches to filter the services. It also shows the branch name and organization name for each service to help users identify the service better."""
    user_pincode = request.user.user_profile.pin_code    
    branch_pincode = Branch.objects.filter(pin_code=user_pincode).values_list('pin_code', flat=True) 
    branches = Branch.objects.filter(services_category=service_category_id,pin_code__in=branch_pincode
    ).distinct()
    return render(request, "queues/services.html", {"services": branches})

def branch_services(request, branch_id):
    """This view shows all the services available in a particular branch, it also shows the price of each service to help users identify the service better."""
    services = Service.objects.filter(branch_id=branch_id)
    for service in services:
        branch = service.branch
        
    return render(request, "queues/branch_services.html", {"services": services,"branch": branch})



@login_required
def add_to_cart(request):    
    if request.method == "POST":
        print('Post method called')
        service_ids = request.POST.getlist("services")
        ic(service_ids,44)

        if not service_ids:
            messages.error(request, "Please select at least one service.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Get branch from first service
        first_service = Service.objects.select_related("branch").get(id=service_ids[0])
        branch = first_service.branch

        # Get or create cart for this user + branch
        cart=Cart.objects.create(
            user=request.user,
            branch=branch
        )        
        for service in service_ids:
            service = Service.objects.get(id=service)

            # Prevent duplicates
            CartItem.objects.get_or_create(
                cart=cart,
                service=service,
                )

        messages.success(request, "Services added to cart.")
        cart_id = cart.id

        return redirect("view_cart",cart_id=cart_id)

    return redirect("customer_dashboard")


@login_required
def view_cart(request, cart_id):     

    cart = Cart.objects.filter(id=cart_id, user=request.user.id).last()
    ic(cart, 55)
    if not cart:
        messages.info(request, "Your cart is empty.")
        return redirect("customer_dashboard")

    cart_items = CartItem.objects.select_related(
        "service",
        "service__branch"
    ).filter(cart=cart_id)

    total_price = cart_items.aggregate(
        total=Sum("service__price")
    )["total"]

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "total_price": total_price
    }
   
    return render(request, "queues/cart.html", context)

def remove_cart_item(request, item_id):
    cart_item = CartItem.objects.filter(id=item_id, cart__user=request.user).first()    
    cart_id=cart_item.pk
    if not cart_item:
        messages.error(request, "Cart item not found.")
        return redirect("view_cart",cart_id)
    
    # cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect("view_cart", cart_id)


def create_token(request,id):
    """This view creates a token for the user based on the items in their cart. It calculates the expected waiting time and service time for the token based on the services in the cart and the current queue at the branch. It also handles edge cases like no one in queue, staff availability, and calculates waiting time accordingly."""    
    #FETCH CART AND ITEMS
    with db_transaction.atomic():
        cart= Cart.objects.select_for_update().filter(user=request.user,id=id).last()
        if not cart:
            messages.error(request, "No active cart found.")
            return redirect("customer_dashboard") 
        cart_items = CartItem.objects.select_for_update().filter(cart=cart).select_related("service")
        #FETCH SERVICES AND BRANCH, CALCULATE EXPECTED SERVICE TIME
        new_expected_service_time = sum(item.service.average_time_minutes for item in cart_items )
        staff = cart.branch.number_of_employees    
        branch = cart.branch
        now = timezone.now()
        #calculate waiting time based on current queue and staff availability
        people_ahead = (
            Token.objects
            .select_for_update()
            .filter(branch=branch, status__in=["waiting", "in_progress"])
        ).count()
        current_serving = Token.objects.select_for_update().filter(branch=branch, status__in=["in_progress"]).count()        
        # Edge Case Handling for Waiting Time Calculation
        if people_ahead == 0 and current_serving < staff:
            print("No one ahead and staff available, starting immediately.")
            waiting_time = 0
            earliest_start_time = now        
            earliest_end_time = earliest_start_time + timezone.timedelta  (minutes=new_expected_service_time)         
        elif people_ahead > 0 and current_serving < staff:
            print("People ahead but staff available, starting immediately after current serving.")
            waiting_time = 0
            earliest_start_time = now        
            earliest_end_time = earliest_start_time + timezone.timedelta(minutes=new_expected_service_time)            
        else:
            print("Calculating waiting time...")        
            
        earliest_token = (
            Token.objects.select_for_update()
            .filter(is_occupied=False,branch=branch,status__in=["in_progress"]
        ).order_by("expected_end_time").first()
        )

        if earliest_token:
            earliest_start_time = earliest_token.expected_end_time

        # lock it
            earliest_token.is_occupied = True
            earliest_token.save(update_fields=["is_occupied"])

        else:
            earliest_start_time = timezone.now()
        earliest_end_time = earliest_start_time + timezone.timedelta(minutes=new_expected_service_time
            )

        waiting_time = max(0,(earliest_start_time - timezone.now()).total_seconds() / 60
        )  
        # Create Token
        token = Token.objects.create(
            branch=branch,
            status="waiting",
            user = User.objects.get(id =request.user.id ),
            expected_start_time=earliest_start_time,
            expected_end_time=earliest_end_time,
            expected_waiting_time=waiting_time,        
            expected_service_time=new_expected_service_time,
            is_occupied=False 
        )
        # Link services to token
        for item in cart_items:
            service=item.service
            branch = item.cart.branch
            TokenService.objects.create(
                token= Token.objects.filter(branch=token.branch,user=request.user.id).last(),
                service=service,
                branch= branch
             )
        # Clear cart_items after creating token
        cart_items.delete()    
        messages.success(request, f"Token {token.token_number} created successfully!")
        # create E-mail notification for user (optional)
        message = f"""
        Hi {request.user.first_name},    
        Welcome to {token.branch.name}!
        Happy to inform you that your token has been generated successfully. Here are the details:
        -------------------------------------------------------------------------------------------   
        Token Number: {token.token_number}
        Expected Waiting Time: {waiting_time:.0f} minutes
        Expected Start Time: {earliest_start_time}
        Expected End Time: {earliest_end_time}

        Thank you!
        """

        send_mail(
            subject="Token Confirmation",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[request.user.email],
            fail_silently=True,
        )
    return redirect("token_detail", token_id=token.id)


@login_required
def token_detail(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch=token.branch
    people_ahead = (
        Token.objects
        .filter(branch=branch, status__in=["waiting", "in_progress"])).count()-1    
    current_serving =Token.objects.filter(branch=branch,status__in=["in_progress"]).count()
    

    # सुरक्षा: ensure user can only view their own token (optional but recommended)
    if token.user != request.user:
        messages.error(request, "You are not authorized to view this token.")
        return redirect("home")

    # fetch services linked to this token
    token_services = TokenService.objects.select_related("service").filter(token=token)
    for service in token_services:
        ic(service)    

    # ✅ REAL-TIME waiting calculation (BEST PRACTICE)
    context= {'token':token,"services":token_services,'waiting_time': token.expected_waiting_time,"current_serving":current_serving,"people_ahead":people_ahead}
    return render(
        request,
        "queues/token_detail.html",
        context
    )

def delete_token(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    # if token.user != request.user:
    #     messages.error(request, "You are not authorized to delete this token.")
    #     return redirect("customer_dashboard", id=token.branch.id)
    token.delete()
    messages.success(request, "Token deleted successfully.")
    return redirect("customer_dashboard", id=token.branch.id)

@login_required
def shop_dashboard(request,id):
    user = request.user
    user_branch = user.user_profile.branch
    id = user_branch.id
    tokens = Token.objects.filter(branch_id=id,
        status__in=["waiting", "in_progress"]
    ).order_by("token_number")
    total_waiting = tokens.filter(status="waiting").count()
    total_in_progress = tokens.filter(status="in_progress").count()
    if total_in_progress > 0: 
        total_waiting_time =tokens.filter(status="in_progress").last().expected_waiting_time 
    else:
        total_waiting_time = 0
    token_data = []    
    
    for token in tokens:        
        start_time = token.start_time        
        expected_start_time = token.expected_start_time
        waiting_time = token.expected_waiting_time
        service_time = token.expected_service_time        
        end_time = start_time + timedelta(minutes=service_time) if start_time else None
        
        
        token_data.append({
            "token": token,
            "waiting_time": waiting_time,            
            "start_time": start_time,
            "service_time":service_time,
            "end_time": end_time,
            "expected_start_time": expected_start_time,
        })
        for token in token_data:
            ic(token["token"].token_number, token["waiting_time"], token["service_time"], token["end_time"])
    return render(request, "queues/shop_dashboard.html", {
        "token_data": token_data,"total_waiting": total_waiting,"total_in_progress": total_in_progress,"total_wait_time": total_waiting_time
    })
@login_required
def start_service(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch_id = token.branch.id

    if token.status != "waiting":
        messages.error(request, "Service already started or completed.")
        return redirect("shop_dashboard",id=branch_id)

    token.status = "in_progress"
    token.start_time = timezone.now()
    token.is_occupied = False
    # token.staff = request.user.staff  # if linked

    token.save()

    messages.success(request, f"Started Token {token.token_number}")
    return redirect("shop_dashboard",id=branch_id)

@login_required
def end_service(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch_id = token.branch.id

    if token.status != "in_progress":
        messages.error(request, "Service not in progress.")
        return redirect("shop_dashboard", id=branch_id)

    token.status = "completed"
    token.end_time = timezone.now()
    token.actual_service_time = (token.end_time - token.start_time).total_seconds() / 60
    token.waiting_time = (token.start_time - token.created_at).total_seconds() / 60

    token.save()

    messages.success(request, f"Completed Token {token.token_number}")
    return redirect("shop_dashboard" ,id=branch_id)


