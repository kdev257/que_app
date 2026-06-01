import datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from login.models import User
from .models import Promotion

class CustomerDashboardTests(TestCase):
    def test_customer_dashboard_displays_active_promotions(self):
        # Create a test user and log in
        user = User.objects.create_user(username='cust_user', password='password123')
        self.client.login(username='cust_user', password='password123')
        
        # Create active promotion
        now = timezone.now()
        active_promo = Promotion.objects.create(
            title="Get 50% Off Grooming!",
            link="https://example.com/promo",
            slot="hero",
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=1),
            is_active=True
        )
        
        # Create inactive promotion
        inactive_promo = Promotion.objects.create(
            title="Expired Offer",
            link="https://example.com/expired",
            slot="hero",
            start_date=now - datetime.timedelta(days=5),
            end_date=now - datetime.timedelta(days=1),
            is_active=True
        )
        
        # Access customer_dashboard
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/customer_dashboard.html")
        
        # Check active promotions are in context and template, inactive are not
        self.assertIn(active_promo, response.context['promotions'])
        self.assertNotIn(inactive_promo, response.context['promotions'])
        self.assertContains(response, "Get 50% Off Grooming!")
        self.assertNotContains(response, "Expired Offer")

    def test_customer_dashboard_displays_popup_promotions(self):
        user = User.objects.create_user(username='cust_user_pop', password='password123')
        self.client.login(username='cust_user_pop', password='password123')
        
        now = timezone.now()
        active_popup = Promotion.objects.create(
            title="10% Cash Back Offier",
            link="https://example.com/cashback",
            slot="popup",
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=1),
            is_active=True
        )
        
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(active_popup, response.context['popup_promotions'])
        self.assertContains(response, "10% Cash Back Offier")
        self.assertContains(response, "id=\"promoModal\"")

    def test_claim_promotion_view(self):
        user = User.objects.create_user(username='claim_user', password='password123')
        self.client.login(username='claim_user', password='password123')
        
        now = timezone.now()
        promo = Promotion.objects.create(
            title="Promo Claim Test",
            link="/queues/services_category/",
            slot="hero",
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=1),
            is_active=True
        )
        
        response = self.client.get(reverse('claim_promotion', args=[promo.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('customer_dashboard'))
        self.assertEqual(self.client.session.get('claimed_promotion_id'), promo.id)

    def test_discount_and_cashback_application_in_cart_and_token(self):
        # Setup branch, service, and cart
        from organization.models import Branch, Organization, Service, Service_Name
        from queues.models import Cart, CartItem, Token
        from .models import PromotionDiscount

        user = User.objects.create_user(username='discount_user', password='password123')
        self.client.login(username='discount_user', password='password123')

        org = Organization.objects.create(name='Test Org Discount', email='d@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Discount', organization=org)
        service_name = Service_Name.objects.create(name='Discount Cut')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=15, price=200.00)

        # Create cart and item
        cart = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart, service=service, quantity=1)

        # Create promotion and discount
        now = timezone.now()
        promo = Promotion.objects.create(
            title="10% Off and Cashback Special",
            link=reverse('view_cart', args=[cart.id]),
            slot="hero",
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=1),
            is_active=True
        )
        PromotionDiscount.objects.create(
            promotion=promo,
            discount_percentage=10.00, # 10%
            cashback_amount=25.00,     # ₹25 cashback
            is_active=True
        )

        # 1. Claim promotion
        self.client.get(reverse('claim_promotion', args=[promo.id]))

        # 2. View Cart
        response = self.client.get(reverse('view_cart', args=[cart.id]))
        self.assertEqual(response.status_code, 200)
        # Verify calculated values in context
        from decimal import Decimal
        self.assertEqual(response.context['discount_amount'], Decimal('20.00')) # 10% of 200 is 20
        self.assertEqual(response.context['final_price'], Decimal('180.00'))
        self.assertEqual(response.context['cashback_amount'], Decimal('25.00'))
        self.assertContains(response, "10% Off and Cashback Special")
        self.assertContains(response, "₹180.00")
        self.assertContains(response, "₹25.00 cashback")

        create_token_response = self.client.post(reverse('create_token', args=[cart.id]), {
            'commute_time': 10
        })
        self.assertEqual(create_token_response.status_code, 302)
        self.client.post(reverse('pay_at_shop', args=[cart.id]))

        # Verify token has persisted the correct values
        token = Token.objects.get(user=user, branch=branch)
        self.assertEqual(token.discount_amount, Decimal('20.00'))
        self.assertEqual(token.final_price, Decimal('180.00'))
        self.assertEqual(token.cashback_amount, Decimal('25.00'))

        # Verify session is cleared
        self.assertNotIn('claimed_promotion_id', self.client.session)

    def test_guest_user_does_not_receive_promotion_benefits(self):
        # Setup branch, service, and guest session
        from organization.models import Branch, Organization, Service, Service_Name
        from queues.models import Cart, CartItem, Token
        from .models import PromotionDiscount
        from login.models import Guest

        # Create guest session and cart
        guest = Guest.objects.create(name='Test Guest', email='guest@test.com', phone_no='9876543210', pin_code='123456')
        session = self.client.session
        session['guest_id'] = guest.id
        session.save()

        org = Organization.objects.create(name='Test Org Guest', email='g@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Guest', organization=org)
        service_name = Service_Name.objects.create(name='Guest Cut')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=15, price=200.00)

        cart = Cart.objects.create(guest=guest, branch=branch)
        CartItem.objects.create(cart=cart, service=service, quantity=1)

        # Create promotion and discount
        now = timezone.now()
        promo = Promotion.objects.create(
            title="Logged Users Only Offer",
            link=reverse('view_cart', args=[cart.id]),
            slot="hero",
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=1),
            is_active=True
        )
        PromotionDiscount.objects.create(
            promotion=promo,
            discount_percentage=10.00,
            cashback_amount=25.00,
            is_active=True
        )

        # 1. Claim promotion
        self.client.get(reverse('claim_promotion', args=[promo.id]))

        # 2. View Cart - should not have discount since it's a guest
        response = self.client.get(reverse('view_cart', args=[cart.id]))
        self.assertEqual(response.status_code, 200)
        from decimal import Decimal
        self.assertEqual(response.context['discount_amount'], Decimal('0.00'))
        self.assertEqual(response.context['final_price'], Decimal('200.00'))
        self.assertEqual(response.context['cashback_amount'], Decimal('0.00'))
        self.assertNotContains(response, "Discount (Logged Users Only Offer)")

        # 3. Create Token - should redirect to checkout
        create_token_response = self.client.post(reverse('create_token', args=[cart.id]), {
            'commute_time': 10
        })
        self.assertEqual(create_token_response.status_code, 302)
        self.client.post(reverse('pay_at_shop', args=[cart.id]))

        token = Token.objects.get(guest=guest, branch=branch)
        self.assertEqual(token.discount_amount, Decimal('0.00'))
        self.assertEqual(token.final_price, Decimal('200.00'))
        self.assertEqual(token.cashback_amount, Decimal('0.00'))

    def test_platform_fees_for_logged_in_and_guest_users(self):
        from organization.models import Branch, Organization, Service, Service_Name
        from queues.models import Cart, CartItem, Token
        from .models import PlatformFee
        from login.models import Guest
        from decimal import Decimal

        # 1. Create a Platform Fee definition
        now = timezone.now()
        fee_setup = PlatformFee.objects.create(
            name="Test Convenience Fee",
            fee_logged_in=Decimal('2.00'),
            fee_guest=Decimal('5.00'),
            is_active=True
        )

        org = Organization.objects.create(name='Test Org Fee', email='fee@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Fee', organization=org)
        service_name = Service_Name.objects.create(name='Fee Cut')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=15, price=200.00)

        # Test Case A: Logged-in User (should pay 2.00 fee)
        user = User.objects.create_user(username='fee_user', password='password123')
        self.client.login(username='fee_user', password='password123')
        
        cart_user = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart_user, service=service, quantity=1)

        # Cart view checks
        response_user = self.client.get(reverse('view_cart', args=[cart_user.id]))
        self.assertEqual(response_user.status_code, 200)
        self.assertEqual(response_user.context['booking_fee'], Decimal('2.00'))
        self.assertEqual(response_user.context['final_price'], Decimal('202.00'))

        # Token checkout checks
        self.client.post(reverse('create_token', args=[cart_user.id]), {'commute_time': 10})
        self.client.post(reverse('pay_at_shop', args=[cart_user.id]))
        token_user = Token.objects.get(user=user, branch=branch)
        self.assertEqual(token_user.booking_fee, Decimal('2.00'))
        self.assertEqual(token_user.final_price, Decimal('202.00'))

        # Test Case B: Guest User (should pay 5.00 fee)
        self.client.logout()
        guest = Guest.objects.create(name='Fee Guest', email='fguest@test.com', phone_no='9876543211', pin_code='123456')
        session = self.client.session
        session['guest_id'] = guest.id
        session.save()

        cart_guest = Cart.objects.create(guest=guest, branch=branch)
        CartItem.objects.create(cart=cart_guest, service=service, quantity=1)

        # Cart view checks
        response_guest = self.client.get(reverse('view_cart', args=[cart_guest.id]))
        self.assertEqual(response_guest.status_code, 200)
        self.assertEqual(response_guest.context['booking_fee'], Decimal('5.00'))
        self.assertEqual(response_guest.context['final_price'], Decimal('205.00'))

        # Token checkout checks
        self.client.post(reverse('create_token', args=[cart_guest.id]), {'commute_time': 10})
        self.client.post(reverse('pay_at_shop', args=[cart_guest.id]))
        token_guest = Token.objects.get(guest=guest, branch=branch)
        self.assertEqual(token_guest.booking_fee, Decimal('5.00'))
        self.assertEqual(token_guest.final_price, Decimal('205.00'))


from unittest.mock import patch, MagicMock

class PaymentCheckoutTests(TestCase):
    def setUp(self):
        from organization.models import Branch, Organization, Service, Service_Name
        from queues.models import Cart, CartItem
        
        self.user = User.objects.create_user(username='pay_user', password='password123')
        self.client.login(username='pay_user', password='password123')
        
        self.org = Organization.objects.create(name='Test Org Pay', email='p@test.com', phone='1234567890')
        self.branch = Branch.objects.create(name='Test Branch Pay', organization=self.org)
        self.service_name = Service_Name.objects.create(name='Pay Cut')
        self.service = Service.objects.create(name=self.service_name, branch=self.branch, average_time_minutes=15, price=200.00)
        
        self.cart = Cart.objects.create(user=self.user, branch=self.branch)
        self.cart_item = CartItem.objects.create(cart=self.cart, service=self.service, quantity=1)

    @patch('razorpay.Client')
    def test_checkout_view_generates_order_and_renders_template(self, mock_razorpay_client):
        mock_client_instance = MagicMock()
        mock_razorpay_client.return_value = mock_client_instance
        mock_client_instance.order.create.return_value = {'id': 'order_test_123'}

        # Post to create_token to store commute_time and booking_date in session and trigger redirection
        response_redirect = self.client.post(reverse('create_token', args=[self.cart.id]), {
            'commute_time': 15,
            'booking_date': '2026-05-30'
        })
        self.assertRedirects(response_redirect, reverse('checkout', args=[self.cart.id]))

        # GET checkout page
        response = self.client.get(reverse('checkout', args=[self.cart.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "queues/checkout.html")
        
        # Verify Razorpay integration context
        self.assertEqual(response.context['razorpay_order_id'], 'order_test_123')
        self.assertEqual(response.context['final_price'], 200.00)
        self.assertContains(response, 'order_test_123')

    def test_pay_at_shop_creates_token_with_correct_status(self):
        from queues.models import Token
        
        # Post to create_token to save details to session
        self.client.post(reverse('create_token', args=[self.cart.id]), {
            'commute_time': 15,
            'booking_date': '2026-05-30'
        })

        # Post to pay_at_shop
        response = self.client.post(reverse('pay_at_shop', args=[self.cart.id]))
        
        # Should redirect to token detail
        tokens = Token.objects.filter(user=self.user, branch=self.branch)
        self.assertEqual(tokens.count(), 1)
        token = tokens.first()
        self.assertRedirects(response, reverse('token_detail', args=[token.id]))
        
        self.assertEqual(token.payment_status, 'pay_at_shop')
        self.assertEqual(token.final_price, 200.00)

    @patch('razorpay.Client')
    def test_payment_callback_success(self, mock_razorpay_client):
        from queues.models import Token
        
        # Setup mock behavior: verify_payment_signature does nothing (success)
        mock_client_instance = MagicMock()
        mock_razorpay_client.return_value = mock_client_instance
        mock_client_instance.utility.verify_payment_signature.return_value = None

        # Post to create_token to save details to session
        self.client.post(reverse('create_token', args=[self.cart.id]), {
            'commute_time': 15,
            'booking_date': '2026-05-30'
        })

        # Post to payment callback
        response = self.client.post(reverse('payment_callback'), {
            'razorpay_payment_id': 'pay_test_999',
            'razorpay_order_id': 'order_test_123',
            'razorpay_signature': 'valid_sig_123',
            'cart_id': self.cart.id
        })

        tokens = Token.objects.filter(user=self.user, branch=self.branch)
        self.assertEqual(tokens.count(), 1)
        token = tokens.first()
        self.assertRedirects(response, reverse('token_detail', args=[token.id]))

        self.assertEqual(token.payment_status, 'paid')
        self.assertEqual(token.razorpay_order_id, 'order_test_123')
        self.assertEqual(token.razorpay_payment_id, 'pay_test_999')

    @patch('razorpay.Client')
    def test_payment_callback_signature_failure(self, mock_razorpay_client):
        from queues.models import Token
        
        # Setup mock behavior: verify_payment_signature raises error
        mock_client_instance = MagicMock()
        mock_razorpay_client.return_value = mock_client_instance
        mock_client_instance.utility.verify_payment_signature.side_effect = Exception("Signature Verification Failed")

        # Post to create_token to save details to session
        self.client.post(reverse('create_token', args=[self.cart.id]), {
            'commute_time': 15,
            'booking_date': '2026-05-30'
        })

        # Post to payment callback with bad credentials
        response = self.client.post(reverse('payment_callback'), {
            'razorpay_payment_id': 'pay_test_999',
            'razorpay_order_id': 'order_test_123',
            'razorpay_signature': 'invalid_sig',
            'cart_id': self.cart.id
        })

        # Should redirect to customer dashboard showing failure, and no token is created
        self.assertRedirects(response, reverse('customer_dashboard'))
        self.assertEqual(Token.objects.filter(user=self.user, branch=self.branch).count(), 0)

