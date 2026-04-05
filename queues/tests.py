from django.test import TestCase
from django.urls import reverse
from .models import Cart, CartItem, Queue, Token
from login.models import User
from organization.models import Branch, Service

class TokenTestCase(TestCase):
    def test_token_creation(self):
    # Create a user, branch, and service for testing
    user = User.objects.create_user(username='testuser', password='testpass')
    branch = Branch.objects.create(name='Test Branch')
    service = Service.objects.create(name='Test Service', average_time_minutes=15)

    # Create a cart and add an item
    cart = Cart.objects.create(user=user, branch=branch)
    CartItem.objects.create(cart=cart, service=service, quantity=1)

    # Simulate creating a token from the cart
    response = self.client.post(reverse('create_token', args=[cart.id]))

    # Check that the token was created successfully
    self.assertEqual(response.status_code, 302)  # Redirect to token detail page
    token = Token.objects.get(user=user, branch=branch)
    self.assertEqual(token.token_number, 1)
    self.assertEqual(token.status, 'waiting')

    
    