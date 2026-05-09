import traceback

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from organization.models import Service, Service_Category, Branch
from accounts.models import Customer
from login.models import User
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
from django.db import transaction as db_transaction
from datetime import datetime, timedelta
from accounts.models import Promotion

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
    #Waiting time calculation for each branch based on current queue and staff availability
    
    return render(request, "queues/services.html", {"services": branches})


def branch_services(request, branch_id):
    # 1. Use get_object_or_404 to prevent crashes if branch_id is invalid
    branch = get_object_or_404(Branch, id=branch_id)
    
    services = Service.objects.filter(branch_id=branch_id)
    is_open = branch.is_open # Direct access since we fetched the object
    
    # 2. Optimize waiting time query (Order by ID or created_at explicitly)
    last_waiting_token = Token.objects.filter(
        branch_id=branch_id, 
        status="waiting"
    ).order_by('id').last()
    
    waiting_time = last_waiting_token.expected_waiting_time if last_waiting_token else 0

    # 3. Calculate queue delay
    last_active_token = Token.objects.filter(
        branch_id=branch_id, 
        status="in_progress"
    ).order_by('id').last()

    queue_delay = 0
    if last_active_token and last_active_token.start_time and last_active_token.expected_start_time:
        diff = (last_active_token.start_time - last_active_token.expected_start_time).total_seconds() / 60
        queue_delay = max(0, diff)
    
    return render(request, "queues/branch_services.html", {
        "services": services,
        "branch": branch,
        "waiting_time": waiting_time,
        "queue_delay": queue_delay,
        "is_open": is_open
    })



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
    # 1. Use .first() instead of .last() for clarity, 
    # and select_related('branch') if you show branch info in the cart
    cart = Cart.objects.filter(id=cart_id, user=request.user).first()
    
    if not cart:
        messages.info(request, "Your cart is empty or does not exist.")
        return redirect("customer_dashboard")

    cart_items = CartItem.objects.select_related(
        "service",
        "service__branch"
    ).filter(cart=cart) # Use the object 'cart' instead of the ID for consistency

    total_price = cart_items.aggregate(
        total=Sum("service__price")
    )["total"] or 0 # 2. Handle 'None' if cart becomes empty

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "total_price": total_price
    }
   
    return render(request, "queues/cart.html", context)

@login_required
def remove_cart_item(request, item_id):
    # 3. Securely fetch the item and the cart ID in one go
    cart_item = CartItem.objects.filter(id=item_id, cart__user=request.user).select_related('cart').first()
    
    if not cart_item:
        messages.error(request, "Item not found.")
        # Fallback if we can't find the cart to redirect to
        return redirect("customer_dashboard")
    
    cart_id = cart_item.cart.id # Get ID before deleting
    cart_item.delete()
    
    messages.success(request, "Item removed from cart.")
    return redirect("view_cart", cart_id=cart_id)


import datetime
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.core.mail import send_mail
from django.conf import settings
# Ensure these are imported correctly in your models/views
# from .models import Cart, CartItem, Token, TokenService

@login_required
def create_token(request, id):
    with db_transaction.atomic():
        # 1. Fetch Cart and Branch
        cart = Cart.objects.select_for_update().filter(user=request.user, id=id).first()
        if not cart:
            messages.error(request, "No active cart found.")
            return redirect("customer_dashboard")
        
        branch = cart.branch
        cart_items = CartItem.objects.filter(cart=cart).select_related("service")
        
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("customer_dashboard")

        # 2. Basic Setup (Using Naive Datetime because USE_TZ=False)
        now = datetime.datetime.now()
        commute_time = int(request.POST.get("commute_time", 0))
        staff_count = branch.number_of_employees or 1
        new_expected_service_time = sum(item.service.average_time_minutes for item in cart_items)
        
        # Setup Today's Opening Time
        opening_time_val = branch.opening_time or datetime.time(8, 0)
        today_opening = datetime.datetime.combine(datetime.date.today(), opening_time_val)

        # 3. Determine Staff Availability
        active_tokens = Token.objects.select_for_update().filter(
            branch=branch, 
            status__in=["waiting", "in_progress"]
        ).order_by("expected_end_time")

        que_size = active_tokens.count()

        if que_size < staff_count:
            # At least one staff member is free
            staff_free_at = max(now, today_opening)
        else:
            # Find the first token in the chain that isn't followed by anyone yet
            earliest_available_token = active_tokens.filter(is_occupied=False).first()
            
            if earliest_available_token:
                staff_free_at = earliest_available_token.expected_end_time
                # Bridge the tokens
                earliest_available_token.is_occupied = True
                earliest_available_token.save(update_fields=['is_occupied'])
            else:
                # Fallback to the absolute end of the line
                last_token = active_tokens.last()
                staff_free_at = last_token.expected_end_time if last_token else today_opening

        # 4. Logical Timing Calculations
        user_arrival_time = now + datetime.timedelta(minutes=commute_time)
        
        # Appointment starts when BOTH staff is free AND user has arrived
        earliest_start_time = max(staff_free_at, user_arrival_time)
        
        # Leave home is (Start Time - Commute)
        leave_home_at = earliest_start_time - datetime.timedelta(minutes=commute_time)
        
        # Wait at Saloon is the gap between arriving and starting
        waiting_at_saloon = max(0, (staff_free_at - user_arrival_time).total_seconds() / 60)
        
        earliest_end_time = earliest_start_time + datetime.timedelta(minutes=new_expected_service_time)

        # 5. Create the Token
        token = Token.objects.create(
            branch=branch,
            status="waiting",
            user=request.user,
            expected_start_time=earliest_start_time,
            expected_end_time=earliest_end_time,
            expected_waiting_time=waiting_at_saloon,
            expected_service_time=new_expected_service_time,
            is_occupied=False 
        )

        # 6. Link Services and Cleanup
        for item in cart_items:
            TokenService.objects.create(
                token=token,
                service=item.service,
                branch=branch
            )

        cart_items.delete()
        cart.delete()
    
    # 7. Email Notification
    # Since USE_TZ=False, token.expected_start_time is already in India Time
    email_message = f"""
    Hi {request.user.first_name},    
    Welcome to {token.branch.name}!
    Your token has been generated successfully. 
    -------------------------------------------   
    Token Number: {token.token_number}
    Expected Wait at Saloon: {token.expected_waiting_time:.0f} mins
    Recommended Leave Time: {leave_home_at.strftime('%I:%M %p')}
    Expected Service Start: {token.expected_start_time.strftime('%I:%M %p')}
    -------------------------------------------
    Thank you for using QuickQueue!
    """

    send_mail(
        subject="Token Confirmation - QuickQueue",
        message=email_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[request.user.email],
        fail_silently=True,
    )

    messages.success(request, f"Token {token.token_number} created successfully!")
    return redirect("token_detail", token_id=token.id)
   

@login_required
def token_detail(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch=token.branch
    people_ahead = (
        Token.objects
        .filter(branch=branch, status__in=["waiting", "in_progress"])).count()-1    
    current_serving =Token.objects.filter(branch=branch,status__in=["in_progress"]).count()
        
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
    token.delete()
    messages.success(request, "Token deleted successfully.")
    return redirect("customer_dashboard", id=token.branch.id)



@transaction.atomic
def cancel_token(request, token_id):
    try:
        # 1. Get the token (only waiting tokens can be cancelled)
        token = Token.objects.select_for_update().get(
            id=token_id,
            status="waiting"
        )

        branch = token.branch

        # 2. Mark token as cancelled
        token.status = "cancelled"
        token.save()

        # 3. Get all waiting tokens of same branch
        waiting_tokens = list(
            Token.objects.select_for_update()
            .filter(branch=branch, status="waiting")
            .order_by("expected_start_time")
        )

        # 4. Determine starting point
        serving_token = Token.objects.filter(
            branch=branch,
            status="in_progress"
        ).order_by("start_time").first()

        if serving_token:
            prev_end_time = serving_token.expected_end_time
        else:
            prev_end_time = timezone.now()

        updated_tokens = []

        # 5. Recalculate queue
        for t in waiting_tokens:
            t.expected_start_time = prev_end_time
            t.expected_end_time = prev_end_time + timedelta(
                minutes=t.expected_service_time
            )

            t.expected_waiting_time = max(
                0,
                int((t.expected_start_time - timezone.now()).total_seconds() / 60)
            )

            prev_end_time = t.expected_end_time
            updated_tokens.append(t)

        # 6. Bulk update
        Token.objects.bulk_update(
            updated_tokens,
            ["expected_start_time", "expected_end_time", "expected_waiting_time"]
        )

        messages.success(request, "Token cancelled and queue updated successfully")

    except Token.DoesNotExist:
        messages.error(request, "Only waiting tokens can be cancelled")

    # 🔁 Redirect back to dashboard (adjust URL name if needed)
    return redirect("customer_home")

@transaction.atomic
def handle_no_show(request, token_id):
    try:
        # 1. Get token (only waiting or serving can be marked no-show)
        token = Token.objects.select_for_update().get(
            id=token_id,
            status__in=["waiting"]
        )

        branch = token.branch

        # 2. Mark as no-show
        token.status = "no_show"
        token.end_time = timezone.now()
        token.save()

        # 3. Get remaining waiting tokens
        waiting_tokens = list(
            Token.objects.select_for_update()
            .filter(branch=branch, status="waiting")
            .order_by("expected_start_time")
        )

        # 4. Determine starting point
        # If someone else is serving → continue from their end
        serving_token = Token.objects.filter(
            branch=branch,
            status="in_progress"
        ).exclude(id=token.id).order_by("start_time").first()

        if serving_token:
            prev_end_time = serving_token.expected_end_time
        else:
            # 👇 KEY DIFFERENCE: immediate start after no-show
            prev_end_time = timezone.now()

        updated_tokens = []

        # 5. Recalculate queue
        for t in waiting_tokens:
            t.expected_start_time = prev_end_time
            t.expected_end_time = prev_end_time + timedelta(
                minutes=t.expected_service_time
            )

            t.expected_waiting_time = max(
                0,
                int((t.expected_start_time - timezone.now()).total_seconds() / 60)
            )

            prev_end_time = t.expected_end_time
            updated_tokens.append(t)

        # 6. Bulk update
        Token.objects.bulk_update(
            updated_tokens,
            ["expected_start_time", "expected_end_time", "expected_waiting_time"]
        )

        messages.success(request, "Token marked as no-show and queue updated")
    except Token.DoesNotExist:
        messages.error(request, "Only waiting  can be marked as no-show")
        # send notification to impacted customers about reduced waiting time due to no-show
                   
        message = f"""
                Hi {t.user.first_name},
                We wanted to inform you that there has been a change in the queue at {t.branch.name} which may affect your expected waiting time. A customer with token number {t.token_number} did not show up for their appointment, which has resulted in a shorter wait time for you. Here are your updated details:
                -------------------------------------------------------------------------------------------
                Token Number: {t.token_number}
                Updated Expected Waiting Time: {t.expected_waiting_time:.0f} minutes
                Updated Expected Start Time: {t.expected_start_time}
                Updated Expected End Time: {t.expected_end_time}
                We apologize for any inconvenience and thank you for your understanding. Please feel free to reach out if you have any questions or need further assistance.
                Thank you!
                """
        send_mail(
                subject="Queue Update Notification",
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[t.user.email],
                fail_silently=True, )
    messages.success(request, f"Token {token.token_number} marked as no-show and impacted customers notified.")        
            
    return redirect("shop_dashboard",branch.id)
         
def customer_home(request):
    # branch = get_object_or_404(Branch, id=id)
    user_tokens = Token.objects.filter(user=request.user).order_by("-created_at")
    context = {
        # "branch": branch,
        "tokens": user_tokens
    }
    return render(request, "queues/customer_home.html", context)

def open_branch(request, id):
    branch = get_object_or_404(Branch, id=id)
    branch.is_open = True
    branch.save()
    messages.success(request, f"{branch.name} is now open.")
    return redirect("shop_dashboard", id=id)


@login_required
def shop_dashboard(request,id):
    user = request.user
    user_branch = user.user_profile.branch
    id = user_branch.id
    if user_branch.is_open == False:
            open_branch(request, id)
    tokens = Token.objects.filter(branch_id=id,
        status__in=["waiting", "in_progress"]
    ).order_by("token_number")
    total_waiting = tokens.filter(status="waiting").count()
    total_in_progress = tokens.filter(status="in_progress").count()
    # if total_in_progress > 0: 
    #     total_waiting_time =tokens.filter(status="in_progress").last().expected_waiting_time 
    # else:
    #     total_waiting_time = 0
    token_data = []    
    waiting_time = 0
    for token in tokens: 
        expected_start_time = token.expected_start_time       
        expected_end_time = token.expected_end_time # based on expected start time + service time, not actual end time
        waiting_time = token.expected_waiting_time       
        service_time = token.expected_service_time
        actual_expected_end_time = token.start_time + timedelta(minutes=service_time) if token.start_time else None # Base om actual start time, not expected start time, to reflect real-time changes in queue   
        # end_time = expected_start_time + timedelta(minutes=service_time)
        
        
        token_data.append({            
            "token": token,
            "waiting_time": waiting_time,            
            "start_time": expected_start_time,
            "service_time":service_time,
            # "end_time": end_time,
            "expected_end_time": expected_end_time,
            "actual_expected_end_time": actual_expected_end_time
        })
        
        
    return render(request, "queues/shop_dashboard.html", {"branch_id":id,
        "token_data": token_data,"total_waiting": total_waiting,"total_in_progress": total_in_progress,"total_wait_time": waiting_time
    })
@login_required
def start_service(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch_id = token.branch.id
    if token.branch.number_of_employees <= Token.objects.filter(branch=token.branch, status="in_progress").count():
        messages.error(request, "No staff available to start this service.")
        return redirect("shop_dashboard", id=branch_id)
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

def close_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_open = False
    branch.save()
    messages.success(request, f"{branch.name} is now closed.")    
    return redirect("logout")    
