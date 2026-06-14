from django.test import TestCase
from django.urls import reverse
from .models import Cart, CartItem, Queue, Token
from login.models import User
from organization.models import Branch, Service, Organization, Service_Name

class TokenTestCase(TestCase):
    def test_token_creation(self):
        # Create a user, branch, and service for testing
        user = User.objects.create_user(username='testuser', password='testpass')
        org = Organization.objects.create(name='Test Org', email='org@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch', organization=org)
        service_name = Service_Name.objects.create(name='Test Service')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=15)

        # Create a cart and add an item
        cart = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart, service=service, quantity=1)

        # Log in the user
        self.client.login(username='testuser', password='testpass')

        # Simulate creating a token from the cart
        response = self.client.post(reverse('create_token', args=[cart.id]))

        # Check that the token was created successfully
        self.assertEqual(response.status_code, 302)  # Redirect to token detail page
        token = Token.objects.get(user=user, branch=branch)
        self.assertEqual(token.token_number, 1)
        self.assertEqual(token.status, 'waiting')

    def test_future_token_creation(self):
        import datetime
        user = User.objects.create_user(username='testuser_future', password='testpass')
        org = Organization.objects.create(name='Test Org Future', email='org_f@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Future', organization=org, opening_time=datetime.time(9, 0), number_of_employees=1)
        service_name = Service_Name.objects.create(name='Test Service Future')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=20)

        # Create a cart and add an item
        cart = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart, service=service, quantity=1)

        # Log in the user
        self.client.login(username='testuser_future', password='testpass')

        # Simulate creating a token from the cart for tomorrow
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.isoformat()
        
        response = self.client.post(reverse('create_token', args=[cart.id]), {
            'commute_time': 15,
            'booking_date': tomorrow_str
        })

        self.assertEqual(response.status_code, 302)
        token = Token.objects.get(user=user, branch=branch)
        self.assertEqual(token.token_date, tomorrow)
        
        # The expected start time should be tomorrow at opening time (09:00) plus commute time (15 mins) -> 09:15
        expected_start = datetime.datetime.combine(tomorrow, datetime.time(9, 0)) + datetime.timedelta(minutes=15)
        self.assertEqual(token.expected_start_time, expected_start)
        
        # The waiting time at the saloon should be 0 because the staff is free at 09:00 and they arrive at 09:15
        self.assertEqual(token.expected_waiting_time, 0)

        # Let's create another token for tomorrow for another user
        user2 = User.objects.create_user(username='testuser_future_2', password='testpass')
        cart2 = Cart.objects.create(user=user2, branch=branch)
        CartItem.objects.create(cart=cart2, service=service, quantity=1)
        
        self.client.login(username='testuser_future_2', password='testpass')
        response2 = self.client.post(reverse('create_token', args=[cart2.id]), {
            'commute_time': 10,
            'booking_date': tomorrow_str
        })
        self.assertEqual(response2.status_code, 302)
        token2 = Token.objects.get(user=user2, branch=branch)
        
        # Since the first token ends at 09:15 + 20 mins = 09:35, the staff is free at 09:35
        # The user2 arrival time is tomorrow 09:00 + 10 mins = 09:10
        # earliest_start_time = max(09:35, 09:10) = 09:35
        # expected_waiting_time = 09:35 - 09:10 = 25 minutes
        self.assertEqual(token2.expected_start_time, datetime.datetime.combine(tomorrow, datetime.time(9, 0)) + datetime.timedelta(minutes=35))
        self.assertEqual(token2.expected_waiting_time, 25)

    def test_htmx_token_status_updates(self):
        user = User.objects.create_user(username='testuser_htmx', password='testpass')
        org = Organization.objects.create(name='Test Org HTMX', email='htmx@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch HTMX', organization=org)
        token = Token.objects.create(user=user, branch=branch, token_number=10, expected_waiting_time=5)
        
        self.client.login(username='testuser_htmx', password='testpass')
        response = self.client.get(reverse('token_status_updates', args=[token.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 mins")
        self.assertTemplateUsed(response, "queues/partials/stats.html")

    def test_htmx_validate_booking_time(self):
        import datetime
        user = User.objects.create_user(username='testuser_val', password='testpass')
        org = Organization.objects.create(name='Test Org Val', email='val@test.com', phone='1234567890')
        branch = Branch.objects.create(
            name='Test Branch Val', 
            organization=org, 
            opening_time=datetime.time(9, 0), 
            closing_time=datetime.time(17, 0),
            number_of_employees=1
        )
        service_name = Service_Name.objects.create(name='Test Service Val')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=60)
        cart = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart, service=service, quantity=1)

        self.client.login(username='testuser_val', password='testpass')
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.isoformat()
        
        response = self.client.post(reverse('validate_booking_time', args=[cart.id]), {
            'commute_time': 60,
            'booking_date': tomorrow_str
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

        response_exceeds = self.client.post(reverse('validate_booking_time', args=[cart.id]), {
            'commute_time': 500,
            'booking_date': tomorrow_str
        })
        self.assertEqual(response_exceeds.status_code, 200)
        self.assertContains(response_exceeds, "Warning:")
        self.assertContains(response_exceeds, "after closing time")

    def test_htmx_shop_dashboard_polling(self):
        import datetime
        user = User.objects.create_user(username='teststaff', password='testpass')
        org = Organization.objects.create(name='Test Org SD', email='sd@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch SD', organization=org)
        
        # Link user to branch via UserProfile
        from login.models import UserProfile
        UserProfile.objects.create(user=user, role='staff', branch=branch, organization=org)
        
        self.client.login(username='teststaff', password='testpass')
        
        response = self.client.get(
            reverse('shop_dashboard', args=[branch.id]),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "queues/partials/dashboard_tokens.html")
        self.assertContains(response, "id=\"dashboard-content\"")
        self.assertContains(response, "hx-trigger=\"every 5s\"")

    def test_queue_recalculation_on_start_service(self):
        import datetime
        from django.utils import timezone
        
        # Create branch with 1 employee
        user = User.objects.create_user(username='teststaff_recalc', password='testpass')
        org = Organization.objects.create(name='Test Org Recalc', email='recalc@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Recalc', organization=org, opening_time=datetime.time(9, 0), number_of_employees=1)
        
        # Link user to branch
        from login.models import UserProfile
        UserProfile.objects.create(user=user, role='staff', branch=branch, organization=org)
        
        # Create 2 tokens for today (one to start, one succeeding waiting token)
        now = timezone.now()
        
        token1 = Token.objects.create(
            branch=branch,
            token_number=1,
            token_date=datetime.date.today(),
            status='waiting',
            expected_start_time=now - datetime.timedelta(minutes=30),
            expected_end_time=now - datetime.timedelta(minutes=10),
            expected_waiting_time=0,
            expected_service_time=20
        )
        
        token2 = Token.objects.create(
            branch=branch,
            token_number=2,
            token_date=datetime.date.today(),
            status='waiting',
            expected_start_time=now - datetime.timedelta(minutes=10),
            expected_end_time=now + datetime.timedelta(minutes=10),
            expected_waiting_time=0,
            expected_service_time=20
        )

        # Log in staff user
        self.client.login(username='teststaff_recalc', password='testpass')

        # Start service for token1
        response = self.client.post(reverse('start_service', args=[token1.id]))
        self.assertEqual(response.status_code, 302)

        # Refresh from DB
        token1.refresh_from_db()
        token2.refresh_from_db()

        self.assertEqual(token1.status, 'in_progress')
        
        # Succeeding token's start time should shift to token1.start_time + 20 mins
        expected_start = token1.start_time + datetime.timedelta(minutes=20)
        self.assertAlmostEqual(
            token2.expected_start_time.timestamp(),
            expected_start.timestamp(),
            delta=5
        )
        
        # Expected waiting time for token2 should be (expected_start - token2_arrival) = 30 minutes
        # token2 arrival was (now - 10 mins) - 0 = now - 10 mins.
        # expected_start is token1.start_time + 20 mins which is close to now + 20 mins.
        # So waiting time should be approximately (now + 20 mins) - (now - 10 mins) = 30 mins.
        self.assertAlmostEqual(token2.expected_waiting_time, 30, delta=1)

    def test_is_occupied_behavior_sequential_tokens(self):
        import datetime
        from django.utils import timezone
        
        # Create branch with 1 employee
        user = User.objects.create_user(username='teststaff_occ', password='testpass')
        org = Organization.objects.create(name='Test Org Occ', email='occ@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch Occ', organization=org, opening_time=datetime.time(9, 0), number_of_employees=1)
        service_name = Service_Name.objects.create(name='Occ Cut')
        service = Service.objects.create(name=service_name, branch=branch, average_time_minutes=20)
        
        # Create first token
        cart1 = Cart.objects.create(user=user, branch=branch)
        CartItem.objects.create(cart=cart1, service=service, quantity=1)
        self.client.login(username='teststaff_occ', password='testpass')
        
        # This will call create_token / _execute_token_creation
        self.client.post(reverse('create_token', args=[cart1.id]), {
            'commute_time': 0,
            'booking_date': datetime.date.today().isoformat()
        })
        
        token1 = Token.objects.get(token_number=1, branch=branch)
        # First token shouldn't be occupied yet
        self.assertFalse(token1.is_occupied)
        
        # Create second token
        user2 = User.objects.create_user(username='teststaff_occ_2', password='testpass')
        cart2 = Cart.objects.create(user=user2, branch=branch)
        CartItem.objects.create(cart=cart2, service=service, quantity=1)
        self.client.login(username='teststaff_occ_2', password='testpass')
        
        self.client.post(reverse('create_token', args=[cart2.id]), {
            'commute_time': 0,
            'booking_date': datetime.date.today().isoformat()
        })
        
        token1.refresh_from_db()
        token2 = Token.objects.get(token_number=2, branch=branch)
        
        # Token 1 should now be marked as occupied
        self.assertTrue(token1.is_occupied)
        # Token 2 should not be occupied
        self.assertFalse(token2.is_occupied)
        
        # Token 2 expected start time should be Token 1's expected end time (no double allocation)
        self.assertEqual(token2.expected_start_time, token1.expected_end_time)

    def test_dynamic_prospective_booking_wait_time(self):
        import datetime
        from django.utils import timezone
        from unittest.mock import patch

        # Create branch with 1 employee
        user = User.objects.create_user(username='testuser_prospective', password='testpass')
        org = Organization.objects.create(name='Test Org Prospective', email='prospective@test.com', phone='1234567890')
        branch = Branch.objects.create(
            name='Test Branch Prospective',
            organization=org,
            number_of_employees=1,
            opening_time=datetime.time(9, 0),
            closing_time=datetime.time(20, 0)
        )

        self.client.login(username='testuser_prospective', password='testpass')

        # Set up an in_progress token taking 20 minutes
        now = timezone.now()
        with patch('django.utils.timezone.now', return_value=now):
            Token.objects.create(
                user=user,
                branch=branch,
                token_number=1,
                token_date=datetime.date.today(),
                status='in_progress',
                start_time=now,
                expected_start_time=now,
                expected_service_time=20,
                expected_end_time=now + datetime.timedelta(minutes=20)
            )

            # Access branch_services and assert context has waiting_time = 20
            response = self.client.get(reverse('branch_services', args=[branch.id]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['waiting_time'], 20)

    def test_branch_admin_blocked_from_customer_dashboard(self):
        import datetime
        from login.models import UserProfile

        # Create branch admin user, organization, branch, and profile
        user = User.objects.create_user(username='test_branch_admin', password='testpass')
        org = Organization.objects.create(name='Test Org AdminBlock', email='block@test.com', phone='1234567890')
        branch = Branch.objects.create(name='Test Branch AdminBlock', organization=org)
        UserProfile.objects.create(user=user, role='branch_admin', branch=branch, organization=org)

        # Log in the branch admin
        self.client.login(username='test_branch_admin', password='testpass')

        # Access customer_dashboard and assert redirect to shop_dashboard
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('shop_dashboard', args=[branch.id]))

        # Access customer_home and assert redirect to shop_dashboard
        response_home = self.client.get(reverse('customer_home'))
        self.assertEqual(response_home.status_code, 302)
        self.assertRedirects(response_home, reverse('shop_dashboard', args=[branch.id]))

    def test_shop_dashboard_redirects_restaurant_to_kitchen_dashboard(self):
        from organization.models import Service_Category
        restaurant_cat = Service_Category.objects.create(name='restaurant')
        org = Organization.objects.create(name='Test Restaurant Org', email='rest@test.com', phone='1234567890')
        restaurant_branch = Branch.objects.create(
            name='Test Restaurant Branch',
            organization=org,
            services_category=restaurant_cat
        )

        user = User.objects.create_user(username='test_rest_admin', password='testpass')
        from login.models import UserProfile
        UserProfile.objects.create(
            user=user,
            role='branch_admin',
            branch=restaurant_branch,
            organization=org
        )

        self.client.login(username='test_rest_admin', password='testpass')

        response = self.client.get(reverse('shop_dashboard', args=[restaurant_branch.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('restaurants:kitchen_dashboard', args=[restaurant_branch.id])
        )

    def test_customer_dashboard_includes_restaurant_category(self):
        from organization.models import Service_Category
        grooming_cat = Service_Category.objects.create(name='Personal Grooming')
        restaurant_cat = Service_Category.objects.create(name='restaurant')
        
        user = User.objects.create_user(username='cust_test', password='testpass')
        self.client.login(username='cust_test', password='testpass')
        
        response = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, grooming_cat.name)
        self.assertContains(response, restaurant_cat.name)

    def test_services_list_redirects_restaurant_category_to_restaurant_search(self):
        from organization.models import Service_Category
        restaurant_cat = Service_Category.objects.create(name='restaurant')
        
        user = User.objects.create_user(username='cust_test_2', password='testpass')
        self.client.login(username='cust_test_2', password='testpass')
        
        response = self.client.get(reverse('services_list', args=[restaurant_cat.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('restaurants:restaurant_search'))

    def test_branch_services_redirects_restaurant_branch_to_menu(self):
        from organization.models import Service_Category
        restaurant_cat = Service_Category.objects.create(name='restaurant')
        org = Organization.objects.create(name='Test Rest Org', email='rest2@test.com', phone='1234567890')
        restaurant_branch = Branch.objects.create(
            name='Test Restaurant Branch 2',
            organization=org,
            services_category=restaurant_cat
        )
        
        user = User.objects.create_user(username='cust_test_3', password='testpass')
        self.client.login(username='cust_test_3', password='testpass')
        
        response = self.client.get(reverse('branch_services', args=[restaurant_branch.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('restaurants:menu_view', args=[restaurant_branch.id]))