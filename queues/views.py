import traceback

from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from login.forms import guest_login_form
from organization.models import Service, Service_Category, Branch
from accounts.models import Customer
from login.models import Guest, User, UserProfile
from icecream import ic
from django.shortcuts import render, redirect
from organization.models import Service
from .models import Cart, CartItem, Token, TokenService
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
import datetime
from django.utils import timezone
# ---------------------------------------------------------------------------
# Helper: resolve the active guest from session (unauthenticated users only)
# ---------------------------------------------------------------------------
def get_guest(request):
    """Return the Guest object stored in the session, or None."""
    guest_id = request.session.get('guest_id')
    if guest_id:
        return Guest.objects.filter(id=guest_id).first()
    return None

# ---------------------------------------------------------------------------
# Decorator: require either an authenticated user or a valid guest session
# ---------------------------------------------------------------------------
from functools import wraps

def login_or_guest_required(view_func):
    """Allow access only if the user is authenticated OR has a valid guest session."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if get_guest(request):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Please log in or continue as a guest to access this page.")
        return redirect('user_login')
    return _wrapped


def customer_required(view_func):
    """
    Decorator for views that checks if the logged-in user is NOT a branch admin.
    If they are, redirect them to their shop dashboard.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                profile = request.user.user_profile
                if profile.role == 'branch_admin':
                    messages.error(request, "Access denied. Branch admins cannot access customer pages.")
                    if profile.branch:
                        return redirect('shop_dashboard', id=profile.branch.id)
                    return redirect('user_profile')
            except UserProfile.DoesNotExist:
                pass
        return view_func(request, *args, **kwargs)
    return _wrapped


# Create your views here.

@customer_required
def service_category(request):
    """Landing page for customers when they login, shows all the service categories available in the system"""
    services = Service_Category.objects.all()
    return render(request, "queues/services.html", {"services": services})

@customer_required
@login_or_guest_required
def service_list(request, service_category_id):
    """
    Shows all services available for a category, filtered by user/guest location.
    """
    if request.user.is_authenticated:
        user_pincode = request.user.user_profile.pin_code
        branch_pincodes = Branch.objects.filter(pin_code=user_pincode).values_list('pin_code', flat=True)
        branches = Branch.objects.filter(
            services_category=service_category_id,
            pin_code__in=branch_pincodes
        ).distinct()
    else:
        # Use the session guest (not the last DB guest) to get the correct pincode
        guest = get_guest(request)
        if guest and guest.pin_code:
            branches = Branch.objects.filter(
                services_category=service_category_id,
                pin_code=guest.pin_code
            ).distinct()
        else:
            # Guest session missing or expired — redirect to guest login
            branches = Branch.objects.none()

    return render(request, "queues/services.html", {"services": branches})

@customer_required
@login_or_guest_required
def branch_services(request, branch_id):
    # 1. Use get_object_or_404 to prevent crashes if branch_id is invalid
    branch = get_object_or_404(Branch, id=branch_id)
    
    # Recalculate queue times dynamically
    today = datetime.date.today()
    recalculate_queue_times(branch, today)
    
    services = Service.objects.filter(branch_id=branch_id)
    is_open = branch.is_open # Direct access since we fetched the object
    
    # Calculate prospective booking wait time dynamically based on the next available staff slot
    next_free_time = get_branch_next_free_time(branch, today)
    now_dt = timezone.now()
    waiting_time = max(0, int((next_free_time - now_dt).total_seconds() / 60))
    
    return render(request, "queues/branch_services.html", {
        "services": services,
        "branch": branch,
        "waiting_time": waiting_time,
        "is_open": is_open
    })



@customer_required
@login_or_guest_required
def add_to_cart(request):
    if request.method == "POST":
        print('Post method called')
        service_ids = request.POST.getlist("services")
        ic(service_ids, 44)

        if not service_ids:
            messages.error(request, "Please select at least one service.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Get branch from first service
        first_service = Service.objects.select_related("branch").get(id=service_ids[0])
        branch = first_service.branch

        # Create cart linked to user OR guest
        if request.user.is_authenticated:
            cart = Cart.objects.create(
                user=request.user,
                branch=branch
            )
        else:
            guest = get_guest(request)
            if not guest:
                messages.error(request, "Please log in as a guest before adding services to your cart.")
                return redirect('guest_login')
            cart = Cart.objects.create(
                guest=guest,
                branch=branch
            )

        for service_id in service_ids:
            service = Service.objects.get(id=service_id)
            CartItem.objects.get_or_create(
                cart=cart,
                service=service,
            )

        messages.success(request, "Services added to cart.")
        cart_id = cart.id
        return redirect("view_cart", cart_id=cart_id)

    return redirect("customer_dashboard")

@customer_required
@login_or_guest_required
def view_cart(request, cart_id):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(id=cart_id, user=request.user).first()
    else:
        guest = get_guest(request)
        if not guest:
            messages.error(request, "Session expired. Please log in as a guest again.")
            return redirect('guest_login')
        cart = Cart.objects.filter(id=cart_id, guest=guest).first()

    if not cart:
        messages.info(request, "Your cart is empty or does not exist.")
        return redirect("customer_dashboard")

    cart_items = CartItem.objects.select_related(
        "service",
        "service__branch"
    ).filter(cart=cart)

    total_price = cart_items.aggregate(
        total=Sum("service__price")
    )["total"] or 0

    from decimal import Decimal
    discount_amount = Decimal('0.00')
    cashback_amount = Decimal('0.00')
    final_price = Decimal(total_price)
    promo_title = None

    claimed_promo_id = request.session.get('claimed_promotion_id')
    if claimed_promo_id and request.user.is_authenticated:
        from accounts.models import PromotionDiscount
        discount_obj = PromotionDiscount.objects.filter(
            promotion_id=claimed_promo_id,
            is_active=True,
            promotion__is_active=True,
            promotion__start_date__lte=timezone.now(),
            promotion__end_date__gte=timezone.now()
        ).first()
        
        if discount_obj:
            promo_title = discount_obj.promotion.title
            if discount_obj.discount_percentage > 0:
                discount_amount = (Decimal(total_price) * discount_obj.discount_percentage / Decimal('100.00')).quantize(Decimal('0.01'))
            if discount_obj.cashback_amount > 0:
                cashback_amount = discount_obj.cashback_amount
            final_price = Decimal(total_price) - discount_amount

    # Retrieve and apply global platform/booking fee
    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
    
    final_price = final_price + booking_fee

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "total_price": total_price,
        "discount_amount": discount_amount,
        "final_price": final_price,
        "cashback_amount": cashback_amount,
        "promo_title": promo_title,
        "booking_fee": booking_fee,
    }

    return render(request, "queues/cart.html", context)

@customer_required
@login_or_guest_required
def remove_cart_item(request, item_id):
    if request.user.is_authenticated:
        cart_item = CartItem.objects.filter(
            id=item_id, cart__user=request.user
        ).select_related('cart').first()
    else:
        guest = get_guest(request)
        cart_item = CartItem.objects.filter(
            id=item_id, cart__guest=guest
        ).select_related('cart').first() if guest else None

    if not cart_item:
        messages.error(request, "Item not found.")
        return redirect("customer_dashboard")

    cart_id = cart_item.cart.id
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
from django.utils.dateparse import parse_date
def _execute_token_creation(request, cart, booking_date, commute_time, payment_status='unpaid', razorpay_order_id=None, razorpay_payment_id=None):
    branch = cart.branch
    cart_items = CartItem.objects.filter(cart=cart).select_related("service")
    if not cart_items.exists():
        return None

    # Setup staff count
    staff_count = branch.number_of_employees or 1
    new_expected_service_time = sum(item.service.average_time_minutes for item in cart_items)

    # Setup Booking Date's Opening Time
    opening_time_val = branch.opening_time or datetime.time(8, 0)
    booking_opening = datetime.datetime.combine(booking_date, opening_time_val)

    # Reference now: if booking is for a future date, reference from opening time
    if booking_date > datetime.date.today():
        reference_now = booking_opening
    else:
        reference_now = datetime.datetime.now()

    # Determine Staff Availability
    active_tokens = Token.objects.filter(
        branch=branch,
        status__in=["waiting", "in_progress"],
        token_date=booking_date
    ).order_by("expected_end_time")

    que_size = active_tokens.count()

    if que_size < staff_count:
        staff_free_at = max(reference_now, booking_opening)
    else:
        earliest_available_token = active_tokens.filter(is_occupied=False).first()
        if earliest_available_token:
            staff_free_at = earliest_available_token.expected_end_time
            earliest_available_token.is_occupied = True
            earliest_available_token.save(update_fields=['is_occupied'])
        else:
            last_token = active_tokens.last()
            if last_token:
                staff_free_at = last_token.expected_end_time
                last_token.is_occupied = True
                last_token.save(update_fields=['is_occupied'])
            else:
                staff_free_at = booking_opening

    # Timing Calculations
    user_arrival_time = reference_now + datetime.timedelta(minutes=commute_time)
    earliest_start_time = max(staff_free_at, user_arrival_time)
    leave_home_at = earliest_start_time - datetime.timedelta(minutes=commute_time)
    waiting_at_saloon = max(0, (staff_free_at - user_arrival_time).total_seconds() / 60)
    earliest_end_time = earliest_start_time + datetime.timedelta(minutes=new_expected_service_time)
    
    queue_delay = 0
    last_active_token = Token.objects.filter(
        branch=branch,
        status__in=["in_progress"],
        token_date=booking_date
    ).order_by("-expected_end_time").first()
    
    if last_active_token and last_active_token.start_time and last_active_token.expected_start_time:
        diff = (last_active_token.start_time - last_active_token.expected_start_time).total_seconds() / 60
        queue_delay = max(0, diff)
    waiting_at_saloon = max(0, waiting_at_saloon + queue_delay)

    # Billing Calculations (Discount & Platform Fee)
    total_price = sum(item.service.price for item in cart_items)
    from decimal import Decimal
    discount_amount = Decimal('0.00')
    cashback_amount = Decimal('0.00')
    final_price = Decimal(total_price)

    claimed_promo_id = request.session.get('claimed_promotion_id')
    if claimed_promo_id and request.user.is_authenticated:
        from accounts.models import PromotionDiscount
        discount_obj = PromotionDiscount.objects.filter(
            promotion_id=claimed_promo_id,
            is_active=True,
            promotion__is_active=True,
            promotion__start_date__lte=timezone.now(),
            promotion__end_date__gte=timezone.now()
        ).first()
        
        if discount_obj:
            if discount_obj.discount_percentage > 0:
                discount_amount = (Decimal(total_price) * discount_obj.discount_percentage / Decimal('100.00')).quantize(Decimal('0.01'))
            if discount_obj.cashback_amount > 0:
                cashback_amount = discount_obj.cashback_amount
            final_price = Decimal(total_price) - discount_amount

    # Retrieve and apply global platform/booking fee
    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
    
    final_price = final_price + booking_fee

    # Create the Token
    token = Token.objects.create(
        branch=branch,
        token_date=booking_date,
        status="waiting",
        user=cart.user,
        guest=cart.guest,
        expected_start_time=earliest_start_time,
        expected_end_time=earliest_end_time,
        expected_waiting_time=waiting_at_saloon,
        expected_service_time=new_expected_service_time,
        is_occupied=False,
        discount_amount=discount_amount,
        final_price=final_price,
        cashback_amount=cashback_amount,
        booking_fee=booking_fee,
        payment_status=payment_status,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id
    )

    # Link Services and Cleanup
    for item in cart_items:
        TokenService.objects.create(
            token=token,
            service=item.service,
            branch=branch
        )

    cart_items.delete()
    cart.delete()

    # Clear the claimed promotion from session on successful booking
    if 'claimed_promotion_id' in request.session:
        del request.session['claimed_promotion_id']

    # Email notification
    if token.user and token.user.email:
        email_message = f"""
    Hi {token.user.first_name},
    Welcome to {token.branch.name}!
    Your token has been generated successfully.
    -------------------------------------------
    Token Number: {token.token_number}
    Expected Wait at Saloon: {token.expected_waiting_time:.0f} mins
    Recommended Leave Time: {leave_home_at.strftime('%I:%M %p')}
    Expected Service Start: {token.expected_start_time.strftime('%I:%M %p')}
    current_token_being_served: {last_active_token.token_number if last_active_token else 'N/A'}
    -------------------------------------------
    Thank you for using QuickQueue!
    """
        send_mail(
            subject="Token Confirmation - QuickQueue",
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[token.user.email],
            fail_silently=True,
        )
    elif token.guest and token.guest.email:
        guest_obj = token.guest
        email_message = f"""
    Hi {guest_obj.name},
    Welcome to {token.branch.name}!
    Your token has been generated successfully.
    -------------------------------------------
    Token Number: {token.token_number}
    Expected Wait at Saloon: {token.expected_waiting_time:.0f} mins
    Recommended Leave Home Time: {leave_home_at.strftime('%I:%M %p')}
    Expected Service Start: {token.expected_start_time.strftime('%I:%M %p')}
    -------------------------------------------
    Thank you for using QuickQueue!
    """
        send_mail(
            subject="Token Confirmation - QuickQueue",
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[guest_obj.email],
            fail_silently=True,
        )

    return token


@customer_required
@login_or_guest_required
def create_token(request, id):
    # Fetch Cart
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, id=id).first()
    else:
        guest = get_guest(request)
        if not guest:
            messages.error(request, "Session expired. Please log in as a guest again.")
            return redirect('guest_login')
        cart = Cart.objects.filter(guest=guest, id=id).first()

    if not cart:
        messages.error(request, "No active cart found.")
        return redirect("customer_dashboard")

    cart_items = CartItem.objects.filter(cart=cart).select_related("service")
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("customer_dashboard")

    # Get timing parameters
    try:
        commute_time = int(request.POST.get("commute_time", 0))
    except (ValueError, TypeError):
        commute_time = 0
        
    booking_date_str = request.POST.get("booking_date")
    if booking_date_str:
        try:
            booking_date = datetime.date.fromisoformat(booking_date_str)
        except ValueError:
            booking_date = datetime.date.today()
    else:
        booking_date = datetime.date.today()

    # Calculate price to decide checkout redirect vs bypass
    total_price = sum(item.service.price for item in cart_items)
    from decimal import Decimal
    discount_amount = Decimal('0.00')
    final_price = Decimal(total_price)

    claimed_promo_id = request.session.get('claimed_promotion_id')
    if claimed_promo_id and request.user.is_authenticated:
        from accounts.models import PromotionDiscount
        discount_obj = PromotionDiscount.objects.filter(
            promotion_id=claimed_promo_id,
            is_active=True,
            promotion__is_active=True,
            promotion__start_date__lte=timezone.now(),
            promotion__end_date__gte=timezone.now()
        ).first()
        
        if discount_obj:
            if discount_obj.discount_percentage > 0:
                discount_amount = (Decimal(total_price) * discount_obj.discount_percentage / Decimal('100.00')).quantize(Decimal('0.01'))
            final_price = Decimal(total_price) - discount_amount

    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
    
    final_price = final_price + booking_fee

    # Store variables in session for later verification/persistence
    request.session['checkout_commute_time'] = commute_time
    request.session['checkout_booking_date'] = booking_date.isoformat()
    request.session['checkout_cart_id'] = cart.id

    # If final price is 0, we can bypass checkout screen and create immediately
    if final_price <= 0:
        with db_transaction.atomic():
            token = _execute_token_creation(
                request, cart, booking_date, commute_time, 
                payment_status='paid'
            )
        if token:
            messages.success(request, f"Token {token.token_number} created successfully!")
            return redirect("token_detail", token_id=token.id)
        else:
            messages.error(request, "Failed to generate token.")
            return redirect("customer_dashboard")

    # Otherwise redirect to checkout page
    return redirect('checkout', cart_id=cart.id)
   

@customer_required
@login_or_guest_required
def token_detail(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch = token.branch
    
    # Recalculate queue times dynamically
    recalculate_queue_times(branch, token.token_date)
    
    people_ahead = (
        Token.objects
        .filter(branch=branch, status__in=["waiting", "in_progress"],token_date=token.token_date )
    ).count() - 1
    current_serving = Token.objects.filter(branch=branch, status__in=["in_progress"],token_date=token.token_date).count()
    # 1. Fetch the token object first
    last_serving_token_obj = Token.objects.filter(
        branch=branch,
        status="in_progress",
        token_date=token.token_date
    ).order_by("-start_time").first()

    # 2. Safely extract the token_number if the object exists, otherwise set to None
    last_serving_token = last_serving_token_obj.token_number if last_serving_token_obj else None

    # Ownership check — works for both users and guests
    if request.user.is_authenticated:
        if token.user != request.user:
            messages.error(request, "You are not authorized to view this token.")
            return redirect("customer_home")
    else:
        guest = get_guest(request)
        if not guest or token.guest != guest:
            messages.error(request, "You are not authorized to view this token.")
            return redirect("customer_dashboard")

    # Fetch services linked to this token
    token_services = TokenService.objects.select_related("service").filter(token=token)
    total_price = sum(item.service.price for item in token_services)
    
    context = {
        'token': token,
        'services': token_services,
        'waiting_time': token.dynamic_waiting_time,
        'current_serving': current_serving,
        'people_ahead': people_ahead,
        'is_guest': not request.user.is_authenticated,
        'last_serving_token': last_serving_token,
        'total_price': total_price,
    }
    return render(request, "queues/token_detail.html", context)

@login_or_guest_required
def delete_token(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch = token.branch
    date = token.token_date
    token.delete()
    recalculate_queue_times(branch, date)
    messages.success(request, "Token deleted successfully.")
    return redirect("customer_dashboard")



@transaction.atomic
@customer_required
@login_or_guest_required
def cancel_token(request, token_id):
    try:
        # 1. Get the token (only waiting tokens can be cancelled)
        token = Token.objects.select_for_update().get(
            id=token_id,
            status="waiting"
        )

        branch = token.branch
        date = token.token_date

        # 2. Mark token as cancelled
        token.status = "cancelled"
        token.save()

        # 3. Recalculate queue
        recalculate_queue_times(branch, date)

        messages.success(request, "Token cancelled and queue updated successfully")

    except Token.DoesNotExist:
        messages.error(request, "Only waiting tokens can be cancelled")

    # 🔁 Redirect back to dashboard (adjust URL name if needed)
    return redirect("customer_home")

@transaction.atomic
@login_required
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
         
@customer_required
@login_required
def customer_home(request):
    import datetime
    from organization.models import Branch
    today = datetime.date.today()
    
    # Recalculate queue times for any branch where user has active bookings today
    active_branches = Token.objects.filter(
        user=request.user,
        status__in=["waiting", "in_progress"],
        token_date=today
    ).values_list("branch", flat=True).distinct()
    
    for branch_id in active_branches:
        try:
            branch = Branch.objects.get(id=branch_id)
            recalculate_queue_times(branch, today)
        except Branch.DoesNotExist:
            pass

    user_tokens = Token.objects.filter(user=request.user).order_by("-created_at")
    context = {
        "tokens": user_tokens
    }
    return render(request, "queues/customer_home.html", context)

@login_required
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
            
    # Recalculate queue times dynamically on page load
    recalculate_queue_times(user_branch, datetime.date.today())
            
    tokens = Token.objects.filter(branch_id=id,
        status__in=["waiting", "in_progress"],token_date=datetime.date.today()
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
        waiting_time = token.dynamic_waiting_time       
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
        
        
    context = {
        "branch_id": id,
        "token_data": token_data,
        "total_waiting": total_waiting,
        "total_in_progress": total_in_progress,
        "total_wait_time": waiting_time
    }
    if request.headers.get('HX-Request') == 'true' or request.META.get('HTTP_HX_REQUEST') == 'true':
        return render(request, "queues/partials/dashboard_tokens.html", context)
    return render(request, "queues/shop_dashboard.html", context)
@login_required
def start_service(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    branch_id = token.branch.id
    if token.branch.number_of_employees <= Token.objects.filter(branch=token.branch, status="in_progress", token_date=datetime.date.today()).count():
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
    recalculate_queue_times(token.branch, token.token_date)

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
    recalculate_queue_times(token.branch, token.token_date)

    messages.success(request, f"Completed Token {token.token_number}")
    return redirect("shop_dashboard" ,id=branch_id)

@login_required
def close_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.is_open = False
    branch.save()
    messages.success(request, f"{branch.name} is now closed.")    
    return redirect("logout")    


# ---------------------------------------------------------------------------
# HTMX Endpoints
# ---------------------------------------------------------------------------

@customer_required
@login_or_guest_required
def token_status_updates(request, token_id):
    """HTMX polling endpoint: returns the updated stats partial for a token."""
    token = get_object_or_404(Token, id=token_id)
    branch = token.branch
    
    # Recalculate queue times dynamically
    recalculate_queue_times(branch, token.token_date)
    
    people_ahead = Token.objects.filter(
        branch=branch,
        status__in=["waiting", "in_progress"],
        token_date=token.token_date
    ).count() - 1
    current_serving = Token.objects.filter(
        branch=branch,
        status__in=["in_progress"],
        token_date=token.token_date
    ).count()
    last_serving_token_obj = Token.objects.filter(
        branch=branch,
        status="in_progress",
        token_date=token.token_date
    ).order_by("-start_time").first()
    last_serving_token = last_serving_token_obj.token_number if last_serving_token_obj else None

    context = {
        'token': token,
        'waiting_time': token.dynamic_waiting_time,
        'current_serving': current_serving,
        'people_ahead': people_ahead,
        'last_serving_token': last_serving_token,
    }
    return render(request, "queues/partials/stats.html", context)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@customer_required
def validate_booking_time(request, cart_id):
    """HTMX endpoint: validates if the estimated service end time exceeds branch closing time."""
    cart = Cart.objects.filter(id=cart_id).first()
    if not cart:
        return HttpResponse("")

    branch = cart.branch
    cart_items = CartItem.objects.filter(cart=cart).select_related("service")
    if not cart_items.exists():
        return HttpResponse("")

    now = datetime.datetime.now()
    try:
        commute_time = int(request.POST.get("commute_time", 0))
    except (ValueError, TypeError):
        commute_time = 0

    booking_date_str = request.POST.get("booking_date")
    if booking_date_str:
        try:
            booking_date = datetime.date.fromisoformat(booking_date_str)
        except ValueError:
            booking_date = datetime.date.today()
    else:
        booking_date = datetime.date.today()

    staff_count = branch.number_of_employees or 1
    new_expected_service_time = sum(item.service.average_time_minutes for item in cart_items)

    opening_time_val = branch.opening_time or datetime.time(8, 0)
    closing_time_val = branch.closing_time or datetime.time(21, 0)
    booking_opening = datetime.datetime.combine(booking_date, opening_time_val)

    if booking_date > datetime.date.today():
        reference_now = booking_opening
    else:
        reference_now = now

    active_tokens = Token.objects.filter(
        branch=branch,
        status__in=["waiting", "in_progress"],
        token_date=booking_date
    ).order_by("expected_end_time")

    que_size = active_tokens.count()

    if que_size < staff_count:
        staff_free_at = max(reference_now, booking_opening)
    else:
        earliest_available_token = active_tokens.filter(is_occupied=False).first()
        if earliest_available_token:
            staff_free_at = earliest_available_token.expected_end_time
        else:
            last_token = active_tokens.last()
            staff_free_at = last_token.expected_end_time if last_token else booking_opening

    user_arrival_time = reference_now + datetime.timedelta(minutes=commute_time)
    earliest_start_time = max(staff_free_at, user_arrival_time)
    earliest_end_time = earliest_start_time + datetime.timedelta(minutes=new_expected_service_time)

    if earliest_end_time.time() > closing_time_val:
        html = f"""
        <div class="alert alert-warning border-0 rounded-3 py-2 px-3 shadow-sm text-start" role="alert" style="font-size: 0.85rem; color: #856404; background-color: #fff3cd; border-color: #ffeeba;">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>Warning:</strong> The estimated service completion time ({earliest_end_time.strftime('%I:%M %p')}) is after closing time ({closing_time_val.strftime('%I:%M %p')}). The service might not be completed.
        </div>
        """
        return HttpResponse(html)

    return HttpResponse("")


@customer_required
def claim_promotion(request, promo_id):
    """View to handle claiming a promotion and storing it in session."""
    promo = get_object_or_404(Promotion, id=promo_id)
    request.session['claimed_promotion_id'] = promo.id
    messages.success(request, f"Promotion '{promo.title}' claimed successfully! It will be applied during checkout.")
    return redirect('customer_dashboard')


@customer_required
@login_or_guest_required
def checkout(request, cart_id):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(id=cart_id, user=request.user).first()
    else:
        guest = get_guest(request)
        if not guest:
            messages.error(request, "Session expired. Please log in as a guest again.")
            return redirect('guest_login')
        cart = Cart.objects.filter(id=cart_id, guest=guest).first()

    if not cart:
        messages.error(request, "The checkout session has expired or the cart was already processed.")
        return redirect("customer_dashboard")

    cart_items = CartItem.objects.filter(cart=cart).select_related("service")
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("customer_dashboard")

    # Load commute_time and booking_date from session
    commute_time = request.session.get('checkout_commute_time', 0)
    booking_date_str = request.session.get('checkout_booking_date')
    if booking_date_str:
        booking_date = datetime.date.fromisoformat(booking_date_str)
    else:
        booking_date = datetime.date.today()

    # Calculate final price
    total_price = sum(item.service.price for item in cart_items)
    from decimal import Decimal
    discount_amount = Decimal('0.00')
    final_price = Decimal(total_price)
    promo_title = None

    claimed_promo_id = request.session.get('claimed_promotion_id')
    if claimed_promo_id and request.user.is_authenticated:
        from accounts.models import PromotionDiscount
        discount_obj = PromotionDiscount.objects.filter(
            promotion_id=claimed_promo_id,
            is_active=True,
            promotion__is_active=True,
            promotion__start_date__lte=timezone.now(),
            promotion__end_date__gte=timezone.now()
        ).first()
        
        if discount_obj:
            promo_title = discount_obj.promotion.title
            if discount_obj.discount_percentage > 0:
                discount_amount = (Decimal(total_price) * discount_obj.discount_percentage / Decimal('100.00')).quantize(Decimal('0.01'))
            final_price = Decimal(total_price) - discount_amount

    # Platform/booking fee
    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
    
    final_price = final_price + booking_fee

    # Create Razorpay Order
    import razorpay
    from django.conf import settings
    
    razorpay_order_id = None
    amount_paise = int(final_price * 100)
    
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"receipt_cart_{cart.id}",
            "payment_capture": 1
        })
        razorpay_order_id = razorpay_order['id']
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Online payment gateway error: {str(e)}. Please choose 'Pay at Shop' or try again later.")
    
    if request.user.is_authenticated:
        user_email = request.user.email
        user_name = f"{request.user.first_name} {request.user.last_name}"
        if hasattr(request.user, 'user_profile') and request.user.user_profile.phone_no:
            user_phone = request.user.user_profile.phone_no
        else:
            user_phone = "9999999999"
    else:
        user_email = guest.email
        user_phone = guest.phone_no
        user_name = guest.name
            
    context = {
        "cart": cart,
        "cart_items": cart_items,
        "total_price": total_price,
        "discount_amount": discount_amount,
        "booking_fee": booking_fee,
        "final_price": final_price,
        "promo_title": promo_title,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount_paise": amount_paise,
        "user_email": user_email,
        "user_phone": user_phone,
        "user_name": user_name,
    }
    
    return render(request, "queues/checkout.html", context)


@customer_required
@login_or_guest_required
def pay_at_shop(request, cart_id):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(id=cart_id, user=request.user).first()
    else:
        guest = get_guest(request)
        if not guest:
            messages.error(request, "Session expired. Please log in as a guest again.")
            return redirect('guest_login')
        cart = Cart.objects.filter(id=cart_id, guest=guest).first()

    if not cart:
        from django.utils import timezone
        from datetime import timedelta
        time_threshold = timezone.now() - timedelta(minutes=2)
        
        if request.user.is_authenticated:
            recent_token = Token.objects.filter(user=request.user, created_at__gte=time_threshold).order_by('-created_at').first()
        else:
            recent_token = Token.objects.filter(guest=guest, created_at__gte=time_threshold).order_by('-created_at').first() if guest else None
            
        if recent_token:
            messages.info(request, "Your booking has already been processed successfully.")
            return redirect('token_detail', token_id=recent_token.id)
            
        messages.error(request, "The checkout session has expired or the cart was already processed.")
        return redirect('customer_dashboard')

    commute_time = request.session.get('checkout_commute_time', 0)
    booking_date_str = request.session.get('checkout_booking_date')
    if booking_date_str:
        booking_date = datetime.date.fromisoformat(booking_date_str)
    else:
        booking_date = datetime.date.today()

    with db_transaction.atomic():
        token = _execute_token_creation(
            request, cart, booking_date, commute_time, 
            payment_status='pay_at_shop'
        )
        
    if token:
        if 'checkout_commute_time' in request.session:
            del request.session['checkout_commute_time']
        if 'checkout_booking_date' in request.session:
            del request.session['checkout_booking_date']
        if 'checkout_cart_id' in request.session:
            del request.session['checkout_cart_id']
            
        messages.success(request, f"Token {token.token_number} created successfully! Please pay at the shop.")
        return redirect('token_detail', token_id=token.id)
    else:
        messages.error(request, "Failed to generate token.")
        return redirect("customer_dashboard")


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@customer_required
@login_or_guest_required
def payment_callback(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id')
        order_id = request.POST.get('razorpay_order_id')
        signature = request.POST.get('razorpay_signature')
        cart_id = request.POST.get('cart_id') or request.GET.get('cart_id') or request.session.get('checkout_cart_id')

        import razorpay
        from django.conf import settings
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
            
            # Fetch Cart
            if request.user.is_authenticated:
                cart = Cart.objects.filter(id=cart_id, user=request.user).first()
            else:
                guest = get_guest(request)
                cart = Cart.objects.filter(id=cart_id, guest=guest).first() if guest else None

            if not cart:
                from django.utils import timezone
                from datetime import timedelta
                time_threshold = timezone.now() - timedelta(minutes=2)
                
                if request.user.is_authenticated:
                    recent_token = Token.objects.filter(user=request.user, created_at__gte=time_threshold).order_by('-created_at').first()
                else:
                    recent_token = Token.objects.filter(guest=guest, created_at__gte=time_threshold).order_by('-created_at').first() if guest else None
                    
                if recent_token:
                    messages.info(request, "Your booking has already been processed successfully.")
                    return redirect('token_detail', token_id=recent_token.id)
                    
                messages.error(request, "The checkout session has expired or the cart was already processed.")
                return redirect('customer_dashboard')

            # Retrieve from session
            commute_time = request.session.get('checkout_commute_time', 0)
            booking_date_str = request.session.get('checkout_booking_date')
            if booking_date_str:
                booking_date = datetime.date.fromisoformat(booking_date_str)
            else:
                booking_date = datetime.date.today()

            with db_transaction.atomic():
                token = _execute_token_creation(
                    request, cart, booking_date, commute_time, 
                    payment_status='paid',
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id
                )

            if token:
                if 'checkout_commute_time' in request.session:
                    del request.session['checkout_commute_time']
                if 'checkout_booking_date' in request.session:
                    del request.session['checkout_booking_date']
                if 'checkout_cart_id' in request.session:
                    del request.session['checkout_cart_id']
                
                messages.success(request, f"Payment Successful! Token {token.token_number} generated.")
                return redirect('token_detail', token_id=token.id)
            else:
                messages.error(request, "Failed to create token after payment.")
                return redirect("customer_dashboard")

        except Exception as e:
            messages.error(request, f"Payment signature verification failed: {str(e)}")
            return redirect("customer_dashboard")
            
    return redirect("customer_dashboard")


def recalculate_queue_times(branch, token_date):
    """
    Recalculates the expected start time, end time, and waiting time for all
    active and waiting tokens of a branch for a given date, based on the actual
    start times of in-progress tokens and the current time.
    """
    from django.utils import timezone
    import datetime

    staff_count = branch.number_of_employees or 1
    now = timezone.now()

    # 1. Get in-progress tokens
    in_progress_tokens = Token.objects.filter(
        branch=branch,
        status="in_progress",
        token_date=token_date
    ).order_by("expected_end_time")

    staff_free_times = []
    staff_last_tokens = []
    
    for tok in in_progress_tokens:
        start = tok.start_time or now
        duration = tok.expected_service_time or 15
        free_time = start + datetime.timedelta(minutes=duration)
        
        tok.is_occupied = False
        if tok.expected_end_time != free_time:
            tok.expected_end_time = free_time
            tok.save(update_fields=['expected_end_time', 'is_occupied'])
        else:
            tok.save(update_fields=['is_occupied'])
            
        staff_free_times.append(free_time)
        staff_last_tokens.append(tok)

    # 2. Fill remaining slots with current time (idle staff free now)
    while len(staff_free_times) < staff_count:
        staff_free_times.append(now)
        staff_last_tokens.append(None)

    # 3. Get waiting tokens
    waiting_tokens = Token.objects.filter(
        branch=branch,
        status="waiting",
        token_date=token_date
    ).order_by("token_number")

    # 4. Simulate queue forward
    for tok in waiting_tokens:
        earliest_idx = staff_free_times.index(min(staff_free_times))
        raw_staff_free_at = staff_free_times[earliest_idx]
        
        # A staff member is available at the expected free time, but no earlier than now
        staff_free_at = max(raw_staff_free_at, now)

        # Calculate the user's targeted arrival time
        wt = tok.expected_waiting_time or 0
        if tok.expected_start_time:
            arrival_time = tok.expected_start_time - datetime.timedelta(minutes=wt)
        else:
            arrival_time = now

        # The token can start when staff is free and user has arrived
        new_start_time = max(staff_free_at, arrival_time)
        new_waiting_time = max(0, (staff_free_at - arrival_time).total_seconds() / 60)
        new_end_time = new_start_time + datetime.timedelta(minutes=tok.expected_service_time or 15)

        # Update the predecessor's occupied flag
        predecessor_tok = staff_last_tokens[earliest_idx]
        if predecessor_tok:
            predecessor_tok.is_occupied = True
            predecessor_tok.save(update_fields=['is_occupied'])

        # New token is not occupied
        tok.is_occupied = False

        # Update the token in the database
        tok.expected_start_time = new_start_time
        tok.expected_end_time = new_end_time
        tok.expected_waiting_time = int(new_waiting_time)
        tok.save(update_fields=['expected_start_time', 'expected_end_time', 'expected_waiting_time', 'is_occupied'])

        # Update the staff free time slot and predecessor
        staff_free_times[earliest_idx] = new_end_time
        staff_last_tokens[earliest_idx] = tok


def get_branch_next_free_time(branch, token_date):
    """
    Simulates the queue to find the earliest time any employee/staff member
    becomes free. This represents the expected start time for a prospective new booking.
    """
    from django.utils import timezone
    import datetime

    staff_count = branch.number_of_employees or 1
    now = timezone.now()

    # 1. Get in-progress tokens
    in_progress_tokens = Token.objects.filter(
        branch=branch,
        status="in_progress",
        token_date=token_date
    ).order_by("expected_end_time")

    staff_free_times = []
    
    for tok in in_progress_tokens:
        start = tok.start_time or now
        duration = tok.expected_service_time or 15
        free_time = start + datetime.timedelta(minutes=duration)
        staff_free_times.append(free_time)

    # 2. Fill remaining slots with current time (idle staff free now)
    while len(staff_free_times) < staff_count:
        staff_free_times.append(now)

    # 3. Get waiting tokens
    waiting_tokens = Token.objects.filter(
        branch=branch,
        status="waiting",
        token_date=token_date
    ).order_by("token_number")

    # 4. Simulate queue forward
    for tok in waiting_tokens:
        earliest_idx = staff_free_times.index(min(staff_free_times))
        raw_staff_free_at = staff_free_times[earliest_idx]
        staff_free_at = max(raw_staff_free_at, now)
        staff_free_times[earliest_idx] = staff_free_at + datetime.timedelta(minutes=tok.expected_service_time or 15)

    # Earliest availability for the next customer
    return min(staff_free_times)


