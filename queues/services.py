from django.db import transaction
from django.utils import timezone
from .models import CartItem, Queue, Token
from django.db import transaction
from django.utils import timezone
import heapq
from django.utils import timezone
from datetime import timedelta, datetime
from icecream import ic
from organization.models import Branch,Service



def generate_token(branch, user):

    today = timezone.localdate()

    with transaction.atomic():

        queue, created = Queue.objects.select_for_update().get_or_create(
            branch=branch,
            date=today,
            defaults={"last_token_number": 0}
        )

        next_number = queue.last_token_number + 1

        token = Token.objects.create(
            queue=queue,
            user=user,
            number=next_number
        )

        queue.last_token_number = next_number
        queue.save()

    return token

from .models import Token, TokenService

def calculate_service_time(services):
    service_time =0
    for service in services:
        service_time += service.average_time_minutes
    return service_time
    
    
import heapq
from django.utils import timezone
import math

def calculate_real_waiting_time(cart):
    """
    cart:
        - cart.branch → Branch object (has number_of_employees)
        - cart.cartitems → each item has service with average_time_minutes
    """

    branch = cart.branch
    num_staff = branch.number_of_employees
    now = timezone.now()

    # Step 1: New customer total service time
    new_service_time = sum(
    item.service.average_time_minutes
    for item in CartItem.objects.filter(cart=cart).select_related("service")
)

    # Step 2: Get active tokens for this branch
    active_tokens = (
        Token.objects
        .filter(branch=branch, status__in=["waiting", "in_progress"])
        
    )

    # Step 3: Separate tokens
    in_service_tokens = [t for t in active_tokens if t.status == "in_service"]
    waiting_tokens = [t for t in active_tokens if t.status == "waiting"]

    # Step 4: Quick shortcut
    if len(in_service_tokens) < num_staff:
        return 0

    # Step 5: Build heap (remaining time of active services)
    staff_heap = []

    for token in in_service_tokens:
    # Step 1: total estimated service time
        total_service_time = sum(
            s.average_time_minutes for s in token.services.all()
        )

        if token.start_time:
        # Step 2: compute expected end time
            elapsed_time = int((now - token.start_time).total_seconds() / 60)

            remaining_time = max(0, total_service_time - elapsed_time)
        else:
        # fallback (should not normally happen)
            remaining_time = total_service_time

    
    heapq.heappush(staff_heap, remaining_time)

    # Step 6: Ensure heap size == num_staff
    # (important if somehow fewer active tokens than staff)
    while len(staff_heap) < num_staff:
        heapq.heappush(staff_heap, 0)

    # Step 7: Simulate waiting queue (FIFO)
    waiting_tokens.sort(key=lambda x: x.created_at)

    for token in waiting_tokens:
        service_time = sum(s.average_time_minutes for s in token.services.all())
        earliest = heapq.heappop(staff_heap)
        heapq.heappush(staff_heap, earliest + service_time)

    # Step 8: New customer waiting time
    waiting_time = heapq.heappop(staff_heap)

    return math.ceil(waiting_time)    

def simulate_barbers(customers, barbers=2):
    """
    customers: list of service times for each customer (minutes)
    barbers: number of barbers (default = 2)
    """

    # Track when each barber becomes free
    barber_free_time = [0] * barbers

    # Store results
    events = []

    current_time = 0

    for i, service_time in enumerate(customers):
        # simulate minute-by-minute time progression
        # not strictly required, but included since you asked for 1-min update
        while True:
            # find earliest free barber
            earliest = min(barber_free_time)

            if earliest <= current_time:
                break  # a barber is free at this minute
            current_time += 1  # move 1 minute forward

        # Assign customer
        barber_index = barber_free_time.index(earliest)
        waiting_time = max(0, earliest - current_time)
        start_time = max(current_time, earliest)
        finish_time = start_time + service_time

        # update barber's availability
        barber_free_time[barber_index] = finish_time

        # store event
        events.append({
            "customer": i + 1,
            "barber": chr(ord('A') + barber_index),
            "start": start_time,
            "wait": waiting_time,
            "finish": finish_time
        })

    return events

simulate_barbers([15,20,45,30])    