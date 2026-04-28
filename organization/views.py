from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from organization.models import Service
from accounts.models import Customer
from queues.services import generate_token




# def create_token(request, service_id, customer_id):
#     service = get_object_or_404(Service, id=service_id)
#     customer = get_object_or_404(Customer, id=customer_id)

#     token = generate_token(service, customer)

#     return JsonResponse({
#         "token_number": token.number,
#         "service": service.name,
#         "date": token.queue.date,
#     })

# Create your views here.
