from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from decimal import Decimal
import datetime

from organization.models import Branch, Service
from queues.models import Token, TokenService
from queues.views import get_guest, login_or_guest_required, customer_required
from .models import (
    MenuCategory, MenuItem, Table, RestaurantOrder, 
    RestaurantOrderItem, RestaurantLandmark, Highway, HighwayBranch
)
from .emails import (
    send_order_placed_email,
    send_order_accepted_email,
    send_order_rejected_email,
    send_payment_confirmed_email,
    send_order_ready_email,
    send_new_order_kitchen_email,
)

# ---------------------------------------------------------------------------
# Search Views & Algorithms
# ---------------------------------------------------------------------------
def search_highway_restaurants(highway_id, current_km, direction, range_km=Decimal('50.00')):
    # 1. Fetch upcoming branches on the selected highway within range (filter only 'restaurant' category)
    query = HighwayBranch.objects.filter(
        highway_id=highway_id,
        branch__services_category__name__iexact='restaurant'
    )
    
    if direction == 'UP':
        hb_list = list(query.filter(
            milestone_km__gt=current_km,
            milestone_km__lte=current_km + range_km,
            direction_of_travel__in=['UP', 'BOTH']
        ).order_by('milestone_km'))
    elif direction == 'DOWN':
        hb_list = list(query.filter(
            milestone_km__lt=current_km,
            milestone_km__gte=current_km - range_km,
            direction_of_travel__in=['DOWN', 'BOTH']
        ).order_by('-milestone_km'))
    else:
        # BOTH directions: filter restaurants within range_km in either direction
        # Keep milestone_km positive/non-negative
        start_range = max(Decimal('0.00'), current_km - range_km)
        end_range = current_km + range_km
        hb_list = list(query.filter(
            milestone_km__gte=start_range,
            milestone_km__lte=end_range
        ).order_by('milestone_km'))
        
    # 2. Identify active exclusivity zones
    exclusivity_zones = []
    for hb in hb_list:
        if hb.is_exclusive and hb.exclusivity_range_km > 0:
            start_blocked = hb.milestone_km - hb.exclusivity_range_km
            end_blocked = hb.milestone_km + hb.exclusivity_range_km
            exclusivity_zones.append((hb.id, start_blocked, end_blocked))
            
    # 3. Filter out competitor outlets in the blocked zones
    final_hb_list = []
    for hb in hb_list:
        is_blocked = False
        for host_id, start_blocked, end_blocked in exclusivity_zones:
            if hb.id != host_id:  # Do not block yourself
                if start_blocked <= hb.milestone_km <= end_blocked:
                    is_blocked = True
                    break
        if not is_blocked:
            final_hb_list.append(hb)
            
    return final_hb_list


@customer_required
@login_or_guest_required
def restaurant_search(request):
    request.session['current_workflow'] = 'restaurant'
    search_type = request.GET.get('search_type', 'urban')
    branches = []
    highways = Highway.objects.all().prefetch_related('segments')
    selected_highway = None
    selected_segment_id = request.GET.get('segment', '')
    
    # Get user location (PIN code) from profile or guest session as a default/fallback
    user_pincode = ""
    if request.user.is_authenticated:
        if hasattr(request.user, 'user_profile'):
            user_pincode = request.user.user_profile.pin_code
    else:
        guest = get_guest(request)
        if guest:
            user_pincode = guest.pin_code

    # Query lists for selection dropdowns
    branches_qs = Branch.objects.filter(services_category__name__iexact='restaurant')
    
    cities = branches_qs.exclude(city__isnull=True).exclude(city='').values_list('city', flat=True).distinct().order_by('city')
    pin_codes = branches_qs.exclude(pin_code__isnull=True).exclude(pin_code='').values_list('pin_code', flat=True).distinct().order_by('pin_code')
    landmarks = RestaurantLandmark.objects.filter(branch__services_category__name__iexact='restaurant').values_list('name', flat=True).distinct().order_by('name')

    if search_type == 'highway':
        highway_id = request.GET.get('highway')
        current_km_str = request.GET.get('current_km', '0')
        direction = request.GET.get('direction', 'BOTH')
        range_km_str = request.GET.get('range_km', '50')
        
        if highway_id:
            selected_highway = get_object_or_404(Highway, id=highway_id)
            try:
                current_km = Decimal(current_km_str)
            except:
                current_km = Decimal('0.00')
                
            try:
                range_km = Decimal(range_km_str)
            except:
                range_km = Decimal('50.00')
                
            final_hb_list = search_highway_restaurants(highway_id, current_km, direction, range_km)
            branches = [hb.branch for hb in final_hb_list]
            
    else:  # Urban Search
        criteria = request.GET.get('criteria', '')
        selected_val = request.GET.get('selected_val', '').strip()
        search_query = request.GET.get('q', '').strip()
        delivery_only = request.GET.get('delivery_only') == 'on'
        
        if delivery_only:
            branches_qs = branches_qs.filter(offers_delivery=True)
            if user_pincode:
                branches_qs = branches_qs.filter(pin_code=user_pincode)
            else:
                branches_qs = branches_qs.none()
        
        if selected_val:
            if criteria == 'city':
                branches = branches_qs.filter(city__iexact=selected_val)
            elif criteria == 'landmark':
                branches = branches_qs.filter(landmarks__name__iexact=selected_val).distinct()
            elif criteria == 'pin_code':
                branches = branches_qs.filter(pin_code__iexact=selected_val)
            else:
                branches = branches_qs
        elif search_query:
            branches = branches_qs.filter(
                Q(name__icontains=search_query) |
                Q(city__icontains=search_query) |
                Q(locality__icontains=search_query) |
                Q(pin_code__icontains=search_query) |
                Q(landmarks__name__icontains=search_query)
            ).distinct()
        elif user_pincode:
            if delivery_only:
                branches = branches_qs
            else:
                branches = branches_qs.filter(pin_code=user_pincode)
                if not branches.exists():
                    branches = branches_qs
        else:
            branches = branches_qs

    delivery_only = request.GET.get('delivery_only') == 'on'

    context = {
        'search_type': search_type,
        'branches': branches,
        'highways': highways,
        'selected_highway': selected_highway,
        'selected_segment_id': selected_segment_id,
        'user_pincode': user_pincode,
        'cities': cities,
        'pin_codes': pin_codes,
        'landmarks': landmarks,
        'delivery_only': delivery_only,
    }
    return render(request, 'restaurants/restaurant_search.html', context)


# ---------------------------------------------------------------------------
# Menu & Cart Views
# ---------------------------------------------------------------------------
@customer_required
@login_or_guest_required
def menu_view(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    categories = MenuCategory.objects.filter(branch=branch).prefetch_related('menu_items')
    
    # Get session cart
    cart = request.session.get('restaurant_cart', {})
    cart_count = sum(cart.values())
    
    # Attach cart quantity to each menu item
    for category in categories:
        for item in category.menu_items.all():
            item.cart_quantity = cart.get(str(item.id), 0)
            
    context = {
        'branch': branch,
        'categories': categories,
        'cart_count': cart_count,
    }
    return render(request, 'restaurants/menu.html', context)


@customer_required
@login_or_guest_required
def add_to_order_cart(request):
    if request.method == "POST":
        menu_item_id = request.POST.get('menu_item_id')
        quantity_str = request.POST.get('quantity', '1')
        branch_id = request.POST.get('branch_id')
        
        try:
            quantity = int(quantity_str)
        except ValueError:
            quantity = 1
            
        menu_item = get_object_or_404(MenuItem, id=menu_item_id)
        
        # Initialize session cart
        cart = request.session.get('restaurant_cart', {})
        
        # If cart contains items from a different branch, reset cart to keep single-restaurant ordering
        cart_branch_id = request.session.get('restaurant_cart_branch_id')
        if cart_branch_id and str(cart_branch_id) != str(branch_id):
            cart = {}
            
        current_qty = cart.get(str(menu_item_id), 0)
        new_qty = current_qty + quantity
        
        if new_qty <= 0:
            cart.pop(str(menu_item_id), None)
            messages.success(request, f"Removed {menu_item.name} from cart.")
        else:
            cart[str(menu_item_id)] = new_qty
            if quantity < 0:
                messages.success(request, f"Reduced quantity of {menu_item.name}.")
            else:
                messages.success(request, f"Added {menu_item.name} to cart.")
        
        request.session['restaurant_cart'] = cart
        if cart:
            request.session['restaurant_cart_branch_id'] = branch_id
        else:
            request.session.pop('restaurant_cart_branch_id', None)
            
        return redirect('restaurants:menu_view', branch_id=branch_id)
        
    return redirect('restaurants:restaurant_search')


@customer_required
@login_or_guest_required
def view_order_cart(request, cart_id=None):
    # Retrieve cart details from session
    cart = request.session.get('restaurant_cart', {})
    branch_id = request.session.get('restaurant_cart_branch_id')
    
    if not cart or not branch_id:
        messages.info(request, "Your order cart is empty.")
        return redirect('restaurants:restaurant_search')
        
    branch = get_object_or_404(Branch, id=branch_id)
    
    cart_items = []
    subtotal = Decimal('0.00')
    
    for item_id, qty in cart.items():
        try:
            menu_item = MenuItem.objects.get(id=item_id)
            total = menu_item.price * qty
            subtotal += total
            cart_items.append({
                'menu_item': menu_item,
                'quantity': qty,
                'total_price': total
            })
        except MenuItem.DoesNotExist:
            pass

    # Retrieve global booking convenience fee
    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
            
    final_price = subtotal + booking_fee
    
    context = {
        'branch': branch,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'booking_fee': booking_fee,
        'final_price': final_price,
    }
    return render(request, 'restaurants/cart.html', context)


@customer_required
@login_or_guest_required
def checkout_order(request, cart_id=None):
    cart = request.session.get('restaurant_cart', {})
    branch_id = request.session.get('restaurant_cart_branch_id')
    
    if not cart or not branch_id:
        messages.error(request, "No active cart found.")
        return redirect('restaurants:restaurant_search')
        
    branch = get_object_or_404(Branch, id=branch_id)
    tables = Table.objects.filter(branch=branch, is_active=True, is_occupied=False)
    
    is_delivery_available = not hasattr(branch, 'highway_info') and branch.offers_delivery
    if request.method == "POST":
        order_type = request.POST.get('order_type', 'dine_in')
        if order_type == 'delivery' and not is_delivery_available:
            messages.error(request, "Delivery is not available for this restaurant.")
            return redirect('restaurants:checkout_order')
        table_id = request.POST.get('table')
        minutes_str = request.POST.get('minutes_until_arrival', '').strip()
        
        # Delivery Address and Payment Options
        delivery_address = None
        payment_status_val = 'unpaid'
        if order_type == 'delivery' and is_delivery_available:
            delivery_address = request.POST.get('delivery_address', '').strip()
            payment_option = request.POST.get('payment_option', 'online')
            if payment_option == 'pay_at_home':
                payment_status_val = 'pay_at_home'
        
        # Capture current user / guest information
        user_obj = request.user if request.user.is_authenticated else None
        guest_obj = get_guest(request) if not request.user.is_authenticated else None
        
        if not user_obj and not guest_obj:
            messages.error(request, "Session expired. Please log in or enter guest details again.")
            return redirect('guest_login')
            
        with timezone.override('Asia/Kolkata'):
            today = datetime.date.today()
            
            # Parse minutes until arrival
            minutes_until_arrival = None
            expected_arrival_dt = None
            if minutes_str:
                try:
                    minutes_until_arrival = int(minutes_str)
                    if minutes_until_arrival > 0:
                        # Compute expected arrival = now + minutes_until_arrival
                        expected_arrival_dt = datetime.datetime.now() + datetime.timedelta(minutes=minutes_until_arrival)
                except (ValueError, TypeError):
                    pass
            
            # Calculate total preparation time for the order based on items
            total_prep_time = 0
            for item_id, qty in cart.items():
                try:
                    menu_item = MenuItem.objects.get(id=item_id)
                    total_prep_time += menu_item.preparation_time_minutes * qty
                except MenuItem.DoesNotExist:
                    pass
            
            # Step 1: Create standard token to link with existing queues structure
            token = Token.objects.create(
                branch=branch,
                token_date=today,
                status="waiting",
                user=user_obj,
                guest=guest_obj,
                expected_service_time=total_prep_time,
                expected_start_time=expected_arrival_dt,
                expected_end_time=(
                    expected_arrival_dt + datetime.timedelta(minutes=total_prep_time)
                    if expected_arrival_dt else None
                ),
                payment_status=payment_status_val
            )
            
            # Step 2: Create Restaurant Order
            selected_table = None
            if order_type == 'dine_in':
                if table_id:
                    selected_table = get_object_or_404(Table, id=table_id)
                else:
                    # Auto-allocate first available table
                    selected_table = Table.objects.filter(branch=branch, is_active=True, is_occupied=False).first()
                
                if selected_table:
                    selected_table.is_occupied = True
                    selected_table.save()
                
            # Set initial order status to pending_confirmation for manual confirmation flow
            order_status_val = 'pending_confirmation'
            
            rest_order = RestaurantOrder.objects.create(
                token=token,
                branch=branch,
                table=selected_table,
                order_type=order_type,
                status=order_status_val,
                estimated_prep_time_minutes=total_prep_time,
                minutes_until_arrival=minutes_until_arrival,
                delivery_address=delivery_address,
                customer_arrived=(order_type == 'delivery')
            )
            
            # Step 3: Populate order items
            for item_id, qty in cart.items():
                menu_item = get_object_or_404(MenuItem, id=item_id)
                RestaurantOrderItem.objects.create(
                    order=rest_order,
                    menu_item=menu_item,
                    quantity=qty,
                    price=menu_item.price
                )
                
            # Clear session cart
            if 'restaurant_cart' in request.session:
                del request.session['restaurant_cart']
            if 'restaurant_cart_branch_id' in request.session:
                del request.session['restaurant_cart_branch_id']
                
            messages.success(request, "Pre-order placed! Waiting for kitchen to accept your order.")

            # Email notifications (fail-safe — never breaks order flow)
            send_order_placed_email(rest_order)
            send_new_order_kitchen_email(rest_order)
                
            return redirect('restaurants:order_status', order_id=rest_order.id)
            
    # Calculate cart total
    subtotal = Decimal('0.00')
    cart_items = []
    for item_id, qty in cart.items():
        menu_item = MenuItem.objects.get(id=item_id)
        total = menu_item.price * qty
        subtotal += total
        cart_items.append({
            'menu_item': menu_item,
            'quantity': qty,
            'total_price': total
        })
        
    user_address = ""
    if request.user.is_authenticated:
        try:
            user_address = request.user.user_profile.address
        except:
            pass

    context = {
        'branch': branch,
        'tables': tables,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'is_delivery_available': is_delivery_available,
        'user_address': user_address,
    }
    return render(request, 'restaurants/checkout.html', context)


# ---------------------------------------------------------------------------
# Order Status Tracking Views
# ---------------------------------------------------------------------------
@customer_required
@login_or_guest_required
def order_status(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    
    # Authorization checks
    if request.user.is_authenticated:
        if order.token.user != request.user:
            messages.error(request, "Unauthorized view.")
            return redirect('restaurants:restaurant_search')
    else:
        guest = get_guest(request)
        if not guest or order.token.guest != guest:
            messages.error(request, "Unauthorized view.")
            return redirect('restaurants:restaurant_search')
            
    if order.status == 'tentative':
        return redirect('restaurants:order_payment', order_id=order.id)
    elif order.status == 'cancelled':
        messages.warning(request, f"We're sorry, the restaurant was unable to confirm your order. Reason: {order.rejection_reason or 'Kitchen overloaded'}")
        return redirect('customer_dashboard')
            
    context = {
        'order': order,
    }
    return render(request, 'restaurants/order_status.html', context)


@never_cache
@customer_required
@login_or_guest_required
def order_status_htmx(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    if order.status == 'tentative':
        from django.urls import reverse
        response = HttpResponse()
        response['HX-Redirect'] = reverse('restaurants:order_payment', args=[order.id])
        return response
    elif order.status == 'cancelled':
        from django.urls import reverse
        messages.warning(request, f"We're sorry, the restaurant was unable to accept your order. Reason: {order.rejection_reason or 'Kitchen overloaded'}")
        response = HttpResponse()
        response['HX-Redirect'] = reverse('customer_dashboard')
        return response
    return render(request, 'restaurants/partials/order_status_card.html', {'order': order})


# ---------------------------------------------------------------------------
# Payment Views
# ---------------------------------------------------------------------------
@customer_required
@login_or_guest_required
def order_payment(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    
    # Check authorization (same as order_status check)
    if request.user.is_authenticated:
        if order.token.user != request.user:
            messages.error(request, "Unauthorized view.")
            return redirect('restaurants:restaurant_search')
    else:
        guest = get_guest(request)
        if not guest or order.token.guest != guest:
            messages.error(request, "Unauthorized view.")
            return redirect('restaurants:restaurant_search')
            
    if order.status != 'tentative':
        messages.info(request, "This order is not awaiting payment.")
        return redirect('restaurants:order_status', order_id=order.id)
        
    subtotal = sum(item.price * item.quantity for item in order.items.all())
    
    # Retrieve platform/booking fee
    from accounts.models import PlatformFee
    active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
    booking_fee = Decimal('0.00')
    if active_fee_obj and active_fee_obj.is_currently_active():
        if request.user.is_authenticated:
            booking_fee = active_fee_obj.fee_logged_in
        else:
            booking_fee = active_fee_obj.fee_guest
            
    final_price = subtotal + booking_fee
    
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
            "receipt": f"receipt_order_{order.id}",
            "payment_capture": 1
        })
        razorpay_order_id = razorpay_order['id']
        
        # Save order ID to token
        token = order.token
        token.razorpay_order_id = razorpay_order_id
        token.booking_fee = booking_fee
        token.final_price = final_price
        token.save()
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.warning(request, f"Online payment gateway offline. You can proceed using the Sandbox Bypass button for testing.")
        
    if request.user.is_authenticated:
        user_email = request.user.email
        user_name = f"{request.user.first_name} {request.user.last_name}"
        if hasattr(request.user, 'user_profile') and request.user.user_profile.phone_no:
            user_phone = request.user.user_profile.phone_no
        else:
            user_phone = "9999999999"
    else:
        guest = get_guest(request)
        user_email = guest.email if guest else "guest@example.com"
        user_phone = guest.phone_no if guest else "9999999999"
        user_name = guest.name if guest else "Guest"
        
    context = {
        "order": order,
        "subtotal": subtotal,
        "booking_fee": booking_fee,
        "final_price": final_price,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_key_id": getattr(settings, 'RAZORPAY_KEY_ID', ''),
        "amount_paise": amount_paise,
        "user_email": user_email,
        "user_phone": user_phone,
        "user_name": user_name,
    }
    
    return render(request, "restaurants/payment.html", context)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@customer_required
@login_or_guest_required
def restaurant_payment_callback(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id')
        order_id = request.POST.get('razorpay_order_id')
        signature = request.POST.get('razorpay_signature')
        
        token = get_object_or_404(Token, razorpay_order_id=order_id)
        order = token.restaurant_order
        
        import razorpay
        from django.conf import settings
        from django.db import transaction as db_transaction
        
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
            
            with db_transaction.atomic():
                # Update Token status
                token.payment_status = 'paid'
                token.status = 'serving'
                token.razorpay_payment_id = payment_id
                token.save()
                
                # Update RestaurantOrder status
                order.status = 'preparing'
                order.save()

            # Notify customer of payment success
            send_payment_confirmed_email(order)
                
            messages.success(request, "Payment successful! Your order is being prepared by the kitchen.")
            return redirect('restaurants:order_status', order_id=order.id)
        except Exception as e:
            messages.error(request, f"Payment verification failed: {str(e)}")
            return redirect('restaurants:order_payment', order_id=order.id)
            
    return redirect('restaurants:restaurant_search')





# ---------------------------------------------------------------------------
# Kitchen & Table Dashboard Views
# ---------------------------------------------------------------------------
@never_cache
@login_required
def kitchen_dashboard(request, branch_id):
    # Verify user is branch admin for this branch or a superuser
    if not request.user.is_superuser:
        from login.models import UserProfile
        try:
            profile = request.user.user_profile
            if profile.role != 'branch_admin' or not profile.branch or profile.branch.id != branch_id:
                messages.error(request, "Access denied.")
                return redirect('user_profile')
        except UserProfile.DoesNotExist:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
        
    branch = get_object_or_404(Branch, id=branch_id)
    
    # Active orders (excluding completed or cancelled)
    orders = RestaurantOrder.objects.filter(
        branch=branch
    ).exclude(
        status__in=['completed', 'cancelled']
    ).order_by('created_at')
    
    pending_count = orders.filter(status='pending_confirmation').count()
    preparing_count = orders.filter(status='preparing').count()
    ready_count = orders.filter(status='ready').count()
    
    tables = Table.objects.filter(branch=branch).order_by('table_number')
    
    context = {
        'branch': branch,
        'orders': orders,
        'tables': tables,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
    }
    if request.headers.get('HX-Request') == 'true' or request.META.get('HTTP_HX_REQUEST') == 'true':
        return render(request, 'restaurants/partials/kitchen_orders_list.html', context)
    return render(request, 'restaurants/kitchen_dashboard.html', context)


@login_required
def accept_order(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if request.method == "POST":
        prep_time = request.POST.get('prep_time', '15')
        table_id = request.POST.get('table')
        
        try:
            order.estimated_prep_time_minutes = int(prep_time)
        except ValueError:
            order.estimated_prep_time_minutes = 15
            
        if order.order_type == 'delivery':
            import datetime
            order.expected_delivery_time = timezone.now() + datetime.timedelta(minutes=order.estimated_prep_time_minutes + 20)
            
        if order.order_type == 'dine_in' and table_id:
            new_table = get_object_or_404(Table, id=table_id)
            # Release old table if a different table is being assigned
            if order.table and order.table.id != new_table.id:
                old_table = order.table
                old_table.is_occupied = False
                old_table.save()
            order.table = new_table
            new_table.is_occupied = True
            new_table.save()
            
        # For pay_at_home orders, bypass tentative/payment flow and start preparing
        if order.token.payment_status == 'pay_at_home':
            order.status = 'preparing'
            order.token.status = 'serving'
            order.token.save()
            if order.order_type == 'delivery':
                order.customer_arrived = True
            messages.success(request, f"Order #{order.id} accepted. Preparing order...")
            
            # Compute and store final price
            subtotal = sum(item.price * item.quantity for item in order.items.all())
            from accounts.models import PlatformFee
            active_fee_obj = PlatformFee.objects.filter(is_active=True).first()
            booking_fee = Decimal('0.00')
            if active_fee_obj and active_fee_obj.is_currently_active():
                if order.token.user:
                    booking_fee = active_fee_obj.fee_logged_in
                else:
                    booking_fee = active_fee_obj.fee_guest
            order.token.final_price = subtotal + booking_fee
            order.token.booking_fee = booking_fee
            order.token.save()
        else:
            order.status = 'tentative'
            messages.success(request, f"Order #{order.id} accepted. Awaiting customer payment.")
            
        order.save()

        # Notify customer (sends complete payment or preparing email depending on payment status)
        send_order_accepted_email(order)
        
    return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)


@login_required
def reject_order(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if request.method == "POST":
        reason = request.POST.get('rejection_reason', 'Kitchen overloaded')
        
        # Release table if one was pre-allocated
        if order.table:
            table = order.table
            table.is_occupied = False
            table.save()
        
        order.status = 'cancelled'
        order.rejection_reason = reason
        order.save()
        
        # Cancel corresponding queue token
        token = order.token
        token.status = 'cancelled'
        token.save()

        # Notify customer of rejection
        send_order_rejected_email(order)
        
        messages.warning(request, f"Order #{order.id} rejected. Reason: {reason}.")
        
    return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)


@login_required
def update_order_status(request, order_id, new_status):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if new_status in dict(RestaurantOrder.STATUS_CHOICES):
        order.status = new_status
        
        # Handle table occupancy release on completion
        if new_status in ['completed', 'cancelled'] and order.table:
            table = order.table
            table.is_occupied = False
            table.save()
            
        # Synchronize token status
        token = order.token
        if new_status == 'completed':
            token.status = 'completed'
            token.save()
        elif new_status == 'cancelled':
            token.status = 'cancelled'
            token.save()
        elif new_status in ['preparing', 'ready', 'served']:
            token.status = 'serving'
            token.save()
            
        order.save()

        # Email: notify customer when food is ready
        if new_status == 'ready':
            send_order_ready_email(order)
            
        messages.success(request, f"Order #{order.id} updated to: {order.get_status_display()}.")
        
    return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)


@login_required
def manage_tables(request, branch_id):
    # Verify user is branch admin for this branch or a superuser
    if not request.user.is_superuser:
        from login.models import UserProfile
        try:
            profile = request.user.user_profile
            if profile.role != 'branch_admin' or not profile.branch or profile.branch.id != branch_id:
                messages.error(request, "Access denied.")
                return redirect('user_profile')
        except UserProfile.DoesNotExist:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
        
    branch = get_object_or_404(Branch, id=branch_id)
    tables = Table.objects.filter(branch=branch).order_by('table_number')
    
    return render(request, 'restaurants/manage_tables.html', {'branch': branch, 'tables': tables})


@login_required
def toggle_table_status(request, table_id):
    table = get_object_or_404(Table, id=table_id)
    branch_id = table.branch.id
    
    # Toggle occupied status
    table.is_occupied = not table.is_occupied
    table.save()
    
    messages.success(request, f"Table {table.table_number} status updated.")
    return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)


@never_cache
@login_required
def staff_dashboard(request, branch_id):
    if not request.user.is_superuser:
        from login.models import UserProfile
        try:
            profile = request.user.user_profile
            if profile.role not in ['staff', 'branch_admin'] or not profile.branch or profile.branch.id != branch_id:
                messages.error(request, "Access denied.")
                return redirect('user_profile')
        except UserProfile.DoesNotExist:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
            
    branch = get_object_or_404(Branch, id=branch_id)
    
    # Active orders (excluding completed, cancelled, pending confirmation, or tentative)
    orders = RestaurantOrder.objects.filter(
        branch=branch
    ).exclude(
        status__in=['completed', 'cancelled', 'pending_confirmation', 'tentative']
    ).order_by('created_at')
    
    # Categories:
    # 1. Awaiting Arrival: not arrived yet
    awaiting_arrival = orders.filter(customer_arrived=False)
    
    # 2. Awaiting Service: arrived, but food is not yet served (preparing or ready)
    awaiting_service = orders.filter(customer_arrived=True, status__in=['preparing', 'ready'])
    
    # 3. Dining: served
    dining = orders.filter(status='served')
    
    context = {
        'branch': branch,
        'awaiting_arrival': awaiting_arrival,
        'awaiting_service': awaiting_service,
        'dining': dining,
    }
    
    if request.headers.get('HX-Request') == 'true' or request.META.get('HTTP_HX_REQUEST') == 'true':
        return render(request, 'restaurants/partials/staff_orders_list.html', context)
    return render(request, 'restaurants/staff_dashboard.html', context)


@login_required
def staff_mark_arrived(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if not request.user.is_superuser:
        profile = request.user.user_profile
        if profile.role not in ['staff', 'branch_admin'] or profile.branch.id != branch_id:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
            
    order.customer_arrived = True
    order.save()
    messages.success(request, f"Customer for Token #{order.token.token_number} marked as ARRIVED.")
    
    if request.headers.get('HX-Request') == 'true':
        from django.urls import reverse
        response = HttpResponse()
        response['HX-Redirect'] = reverse('restaurants:staff_dashboard', args=[branch_id])
        return response
    return redirect('restaurants:staff_dashboard', branch_id=branch_id)


@login_required
def staff_mark_served(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if not request.user.is_superuser:
        profile = request.user.user_profile
        if profile.role not in ['staff', 'branch_admin'] or profile.branch.id != branch_id:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
            
    order.status = 'served'
    order.save()
    
    token = order.token
    token.status = 'serving'
    token.save()
    
    messages.success(request, f"Order #{order.id} (Token #{order.token.token_number}) marked as SERVED.")
    
    if request.headers.get('HX-Request') == 'true':
        from django.urls import reverse
        response = HttpResponse()
        response['HX-Redirect'] = reverse('restaurants:staff_dashboard', args=[branch_id])
        return response
    return redirect('restaurants:staff_dashboard', branch_id=branch_id)


@login_required
def staff_mark_completed(request, order_id):
    order = get_object_or_404(RestaurantOrder, id=order_id)
    branch_id = order.branch.id
    
    if not request.user.is_superuser:
        profile = request.user.user_profile
        if profile.role not in ['staff', 'branch_admin'] or profile.branch.id != branch_id:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
            
    order.status = 'completed'
    order.save()
    
    if order.table:
        table = order.table
        table.is_occupied = False
        table.save()
        
    token = order.token
    token.status = 'completed'
    token.save()
    
    messages.success(request, f"Order #{order.id} (Token #{order.token.token_number}) marked as COMPLETED.")
    
    if request.headers.get('HX-Request') == 'true':
        from django.urls import reverse
        response = HttpResponse()
        response['HX-Redirect'] = reverse('restaurants:staff_dashboard', args=[branch_id])
        return response
    return redirect('restaurants:staff_dashboard', branch_id=branch_id)


@login_required
def toggle_delivery_status(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    
    if not request.user.is_superuser:
        from login.models import UserProfile
        try:
            profile = request.user.user_profile
            if profile.role != 'branch_admin' or not profile.branch or profile.branch.id != branch_id:
                messages.error(request, "Access denied.")
                return redirect('user_profile')
        except UserProfile.DoesNotExist:
            messages.error(request, "Access denied.")
            return redirect('user_profile')
            
    if hasattr(branch, 'highway_info'):
        messages.error(request, "Highway branches cannot offer home delivery.")
        return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)
        
    branch.offers_delivery = not branch.offers_delivery
    branch.save()
    
    status_str = "started" if branch.offers_delivery else "stopped"
    messages.success(request, f"Home delivery option has been {status_str} for this restaurant.")
    return redirect('restaurants:kitchen_dashboard', branch_id=branch_id)


