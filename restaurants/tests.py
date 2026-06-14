from django.test import TestCase
from decimal import Decimal
from organization.models import Organization, Branch
from .models import Highway, HighwayBranch, RestaurantLandmark
from .views import search_highway_restaurants

class RestaurantSearchTests(TestCase):
    def setUp(self):
        # 1. Create Organization
        self.org = Organization.objects.create(
            name="Highway Food Group",
            email="info@highwayfood.com",
            phone="1234567890"
        )
        
        # 1.5. Create Service Category
        from organization.models import Service_Category
        self.category_restaurant = Service_Category.objects.create(
            name="restaurant"
        )
        
        # 2. Create Highway
        self.highway = Highway.objects.create(
            name="NH-44",
            start_point="Delhi",
            end_point="Agra"
        )
        
        # 3. Create Branches
        self.branch_km50 = Branch.objects.create(
            organization=self.org,
            services_category=self.category_restaurant,
            name="KM 50 Highway Rest",
            address="KM 50, NH-44",
            city="Delhi NCR",
            locality="Kundli",
            pin_code="131028"
        )
        
        self.branch_km80 = Branch.objects.create(
            organization=self.org,
            services_category=self.category_restaurant,
            name="KM 80 Highway Rest (Exclusive)",
            address="KM 80, NH-44",
            city="Panipat Outskirts",
            locality="Samalkha",
            pin_code="132101"
        )
        
        self.branch_km85 = Branch.objects.create(
            organization=self.org,
            services_category=self.category_restaurant,
            name="KM 85 Competitor Rest",
            address="KM 85, NH-44",
            city="Panipat",
            locality="Gharaunda",
            pin_code="132103"
        )
        
        self.branch_km120 = Branch.objects.create(
            organization=self.org,
            services_category=self.category_restaurant,
            name="KM 120 Highway Rest",
            address="KM 120, NH-44",
            city="Karnal",
            locality="Karnal Bypass",
            pin_code="132001"
        )

        # 4. Create HighwayBranches mapping milestones
        self.hb_km50 = HighwayBranch.objects.create(
            branch=self.branch_km50,
            highway=self.highway,
            milestone_km=Decimal('50.00'),
            direction_of_travel='BOTH',
            is_exclusive=False
        )
        
        self.hb_km80 = HighwayBranch.objects.create(
            branch=self.branch_km80,
            highway=self.highway,
            milestone_km=Decimal('80.00'),
            direction_of_travel='UP', # Only accessible going UP
            is_exclusive=True,
            exclusivity_range_km=Decimal('10.00') # Blocks anything between KM 70 and KM 90
        )
        
        self.hb_km85 = HighwayBranch.objects.create(
            branch=self.branch_km85,
            highway=self.highway,
            milestone_km=Decimal('85.00'),
            direction_of_travel='BOTH',
            is_exclusive=False
        )
        
        self.hb_km120 = HighwayBranch.objects.create(
            branch=self.branch_km120,
            highway=self.highway,
            milestone_km=Decimal('120.00'),
            direction_of_travel='BOTH',
            is_exclusive=False
        )

        # 5. Create Landmark for urban searches
        RestaurantLandmark.objects.create(
            branch=self.branch_km120,
            name="Near Karnal Lake"
        )

    def test_urban_landmark_search(self):
        """Test that urban search queries match by name, locality, or landmarks."""
        # Search by name keyword
        results = Branch.objects.filter(name__icontains="Competitor")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.branch_km85)
        
        # Search by landmark
        results_landmark = Branch.objects.filter(landmarks__name__icontains="Karnal Lake")
        self.assertEqual(results_landmark.count(), 1)
        self.assertEqual(results_landmark.first(), self.branch_km120)

    def test_highway_direction_filtering(self):
        """Test that highway search filters branches in the direction of travel."""
        # Heading UP from KM 40, expecting branches at KM 50, 80 (since UP), 85, 120
        # Wait, the search_highway_restaurants function matches direction_of_travel__in=['UP', 'BOTH'] when direction == 'UP'
        # So it should find KM 50 (BOTH), KM 80 (UP), KM 85 (BOTH), KM 120 (BOTH)
        # However, because KM 80 is exclusive (10km), KM 85 is within its exclusivity zone [70, 90] and should be filtered out!
        # Let's test without exclusivity first: if we search at KM 40 with range 30, we expect KM 50.
        results = search_highway_restaurants(self.highway.id, Decimal('40.00'), 'UP', Decimal('30.00'))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].branch, self.branch_km50)
        
        # Heading DOWN from KM 100, expecting branches at KM 85, 50 (KM 80 is UP only, so it shouldn't show in DOWN search)
        results_down = search_highway_restaurants(self.highway.id, Decimal('100.00'), 'DOWN', Decimal('60.00'))
        # KM 85 is in range. KM 50 is in range. KM 80 is UP only, so it is filtered out.
        # Thus, exclusivity of KM 80 doesn't affect DOWN search for KM 85.
        self.assertEqual(len(results_down), 2)
        self.assertEqual(results_down[0].branch, self.branch_km85)
        self.assertEqual(results_down[1].branch, self.branch_km50)

    def test_highway_exclusivity_blocking(self):
        """Test that premium exclusive branches correctly filter out nearby competitors."""
        # Heading UP from KM 60, range 70 (covers up to KM 130).
        # Normal upcoming branches: KM 80 (UP), KM 85 (BOTH), KM 120 (BOTH)
        # But KM 80 has exclusivity of 10km (blocks range 70 to 90).
        # KM 85 falls in [70, 90], so it must be filtered out!
        # Expecting only: KM 80 and KM 120.
        results = search_highway_restaurants(self.highway.id, Decimal('60.00'), 'UP', Decimal('70.00'))
        
        self.assertEqual(len(results), 2)
        # KM 80 (UP) should show
        self.assertEqual(results[0].branch, self.branch_km80)
        # KM 120 should show
        self.assertEqual(results[1].branch, self.branch_km120)
        # Competitor at KM 85 should NOT be present
        branch_ids = [r.branch.id for r in results]
        self.assertNotIn(self.branch_km85.id, branch_ids)

    def test_highway_segment_creation_and_context(self):
        """Test that HighwaySegment can be created and is returned in context of search view."""
        from login.models import User
        user = User.objects.create_user(username="search_test_user_1", password="testpass")
        self.client.login(username="search_test_user_1", password="testpass")

        from restaurants.models import HighwaySegment
        segment = HighwaySegment.objects.create(
            highway=self.highway,
            start_place="Delhi",
            end_place="Panipat",
            start_km=Decimal('0.00'),
            end_km=Decimal('85.00')
        )
        
        # Test string representation
        self.assertEqual(str(segment), "Delhi to Panipat on NH-44 (KM 0.00 -> 85.00)")
        
        # Request search view
        from django.urls import reverse
        response = self.client.get(reverse('restaurants:restaurant_search') + "?search_type=highway")
        self.assertEqual(response.status_code, 200)
        
        # Check highways list is in context and contains the segment
        highways = list(response.context['highways'])
        self.assertIn(self.highway, highways)
        
        # Verify segment is prefetched and exists under self.highway
        highway_from_context = next(h for h in highways if h.id == self.highway.id)
        segments = list(highway_from_context.segments.all())
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0], segment)

    def test_highway_search_by_segment_simulation(self):
        """Test searching with parameters populated from segment selection."""
        from login.models import User
        user = User.objects.create_user(username="search_test_user_2", password="testpass")
        self.client.login(username="search_test_user_2", password="testpass")

        from restaurants.models import HighwaySegment
        segment = HighwaySegment.objects.create(
            highway=self.highway,
            start_place="Delhi",
            end_place="Panipat",
            start_km=Decimal('0.00'),
            end_km=Decimal('85.00')
        )
        
        # Simulate form submission: segment is Delhi to Panipat, so current_km=0.00, direction=UP
        # We search with range_km=90.00
        from django.urls import reverse
        response = self.client.get(reverse('restaurants:restaurant_search'), {
            'search_type': 'highway',
            'highway': self.highway.id,
            'segment': segment.id,
            'current_km': '0.00',
            'direction': 'UP',
            'range_km': '90.00'
        })
        
        self.assertEqual(response.status_code, 200)
        # Verify branches returned are branches in the range heading UP (KM 50 and KM 80; KM 85 Competitor is blocked)
        branches = list(response.context['branches'])
        self.assertEqual(len(branches), 2)
        self.assertIn(self.branch_km50, branches)
        self.assertIn(self.branch_km80, branches)
        self.assertNotIn(self.branch_km85, branches)

    def test_highway_branch_segment_matching_validation(self):
        """Test that segment assigned to HighwayBranch must belong to the same highway."""
        from django.core.exceptions import ValidationError
        from restaurants.models import HighwaySegment, HighwayBranch
        
        # 1. Create a segment on self.highway
        segment_ok = HighwaySegment.objects.create(
            highway=self.highway,
            start_place="Delhi",
            end_place="Panipat",
            start_km=Decimal('0.00'),
            end_km=Decimal('85.00')
        )
        
        # 2. Create another highway
        from restaurants.models import Highway
        other_highway = Highway.objects.create(
            name="NH-8",
            start_point="Delhi",
            end_point="Jaipur"
        )
        segment_bad = HighwaySegment.objects.create(
            highway=other_highway,
            start_place="Delhi",
            end_place="Gurugram",
            start_km=Decimal('0.00'),
            end_km=Decimal('30.00')
        )
        
        # Assigning segment_ok to hb_km50 should work
        self.hb_km50.segment = segment_ok
        self.hb_km50.save() # Should pass clean() without errors
        self.assertEqual(self.hb_km50.segment, segment_ok)
        
        # Assigning segment_bad to hb_km50 should raise ValidationError
        self.hb_km50.segment = segment_bad
        with self.assertRaises(ValidationError):
            self.hb_km50.save()

    def test_highway_branch_segment_restaurant_only_validation(self):
        """Test that segment can only be assigned to a restaurant branch."""
        from django.core.exceptions import ValidationError
        from organization.models import Service_Category, Branch
        from restaurants.models import HighwaySegment, HighwayBranch
        
        # Create non-restaurant branch
        cat_non_rest = Service_Category.objects.create(name="hotel")
        branch_non_rest = Branch.objects.create(
            organization=self.org,
            services_category=cat_non_rest,
            name="Highway Hotel",
            address="KM 60"
        )
        
        # Create a segment
        segment = HighwaySegment.objects.create(
            highway=self.highway,
            start_place="Delhi",
            end_place="Panipat",
            start_km=Decimal('0.00'),
            end_km=Decimal('85.00')
        )
        
        # Create HighwayBranch config for the non-restaurant branch
        hb = HighwayBranch(
            branch=branch_non_rest,
            highway=self.highway,
            milestone_km=Decimal('60.00'),
            segment=segment
        )
        
        # Saving should raise ValidationError because the branch is not a restaurant
        with self.assertRaises(ValidationError):
            hb.save()


class RestaurantOrderTests(TestCase):
    def setUp(self):
        from organization.models import Organization, Branch, Service_Category
        from restaurants.models import MenuItem, MenuCategory, Table, MenuCategoryName, GlobalMenuItem
        self.org = Organization.objects.create(name="Rest Org Test", email="test@rest.com", phone="1234")
        self.cat = Service_Category.objects.create(name="restaurant")
        self.branch = Branch.objects.create(organization=self.org, services_category=self.cat, name="Test Branch")
        self.menu_cat_name = MenuCategoryName.objects.create(name="Food")
        self.menu_cat = MenuCategory.objects.create(branch=self.branch, name=self.menu_cat_name)
        self.global_item = GlobalMenuItem.objects.create(name="Pizza", is_veg=True)
        self.item = MenuItem.objects.create(category=self.menu_cat, name=self.global_item, price=Decimal('200.00'), preparation_time_minutes=15)
        self.table1 = Table.objects.create(branch=self.branch, table_number="1", capacity=4)
        self.table2 = Table.objects.create(branch=self.branch, table_number="2", capacity=2)
        
        from login.models import User
        self.user = User.objects.create_user(username="cust_order_test", password="testpass")

    def test_checkout_creates_pending_order(self):
        self.client.login(username="cust_order_test", password="testpass")
        
        # Populate session cart
        session = self.client.session
        session['restaurant_cart'] = {str(self.item.id): 2}
        session['restaurant_cart_branch_id'] = self.branch.id
        session.save()
        
        # Post to checkout view (with minutes_until_arrival)
        from django.urls import reverse
        response = self.client.post(reverse('restaurants:checkout_order'), {
            'order_type': 'dine_in',
            'table': self.table1.id,
            'minutes_until_arrival': '20',
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify order was created with status 'pending_confirmation'
        from restaurants.models import RestaurantOrder
        order = RestaurantOrder.objects.first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'pending_confirmation')
        self.assertEqual(order.table, self.table1)
        self.assertEqual(order.token.payment_status, 'unpaid')
        
        # Verify table is marked occupied
        self.table1.refresh_from_db()
        self.assertTrue(self.table1.is_occupied)

    def test_checkout_saves_arrival_time(self):
        """Verify that minutes_until_arrival is saved on the order and token times are computed."""
        self.client.login(username="cust_order_test", password="testpass")
        
        session = self.client.session
        session['restaurant_cart'] = {str(self.item.id): 1}
        session['restaurant_cart_branch_id'] = self.branch.id
        session.save()
        
        from django.urls import reverse
        self.client.post(reverse('restaurants:checkout_order'), {
            'order_type': 'dine_in',
            'table': self.table1.id,
            'minutes_until_arrival': '30',
        })
        
        from restaurants.models import RestaurantOrder
        order = RestaurantOrder.objects.first()
        self.assertIsNotNone(order)
        # minutes_until_arrival should be stored on the order
        self.assertEqual(order.minutes_until_arrival, 30)
        # Token should have expected_start_time set (now + 30 mins)
        self.assertIsNotNone(order.token.expected_start_time)
        # Token expected_end_time should be arrival + prep_time
        self.assertIsNotNone(order.token.expected_end_time)
        self.assertGreater(order.token.expected_end_time, order.token.expected_start_time)

    def test_cancelled_order_redirects_customer(self):
        self.client.login(username="cust_order_test", password="testpass")
        
        # Create cancelled order
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="cancelled",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='cancelled',
            rejection_reason="No inventory"
        )
        
        # Request order_status page
        from django.urls import reverse
        response = self.client.get(reverse('restaurants:order_status', args=[order.id]))
        
        # Should redirect to customer_dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn('/acc/customer_dashboard/', response.url)

    def test_cancelled_order_htmx_redirects_customer(self):
        self.client.login(username="cust_order_test", password="testpass")
        
        # Create cancelled order
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="cancelled",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='cancelled',
            rejection_reason="No inventory"
        )
        
        # Request order_status_htmx page
        from django.urls import reverse
        response = self.client.get(reverse('restaurants:order_status_htmx', args=[order.id]), HTTP_HX_REQUEST='true')
        
        # Should return response with HX-Redirect header
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('HX-Redirect'), '/acc/customer_dashboard/')

    def test_default_acceptance_auto_table_allocation(self):
        self.client.login(username="cust_order_test", password="testpass")
        
        # Populate session cart
        session = self.client.session
        session['restaurant_cart'] = {str(self.item.id): 1}
        session['restaurant_cart_branch_id'] = self.branch.id
        session.save()
        
        # Post to checkout view with table="" (Seat me automatically)
        from django.urls import reverse
        response = self.client.post(reverse('restaurants:checkout_order'), {
            'order_type': 'dine_in',
            'table': ''
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify first free table (table1) was allocated and marked occupied
        from restaurants.models import RestaurantOrder
        order = RestaurantOrder.objects.first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'pending_confirmation')
        self.assertEqual(order.table, self.table1)
        
        self.table1.refresh_from_db()
        self.assertTrue(self.table1.is_occupied)
        
        # table2 should still be vacant
        self.table2.refresh_from_db()
        self.assertFalse(self.table2.is_occupied)

    def test_kitchen_accept_order_changes_to_tentative(self):
        # Create a user for staff (branch admin or superuser)
        from login.models import User
        staff_user = User.objects.create_superuser(username="staff_user", password="staffpass")
        self.client.login(username="staff_user", password="staffpass")
        
        # Create a pending order
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="waiting",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='pending_confirmation'
        )
        
        # Post to accept_order view
        from django.urls import reverse
        response = self.client.post(reverse('restaurants:accept_order', args=[order.id]), {
            'prep_time': '20',
            'table': self.table1.id
        })
        
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        
        # Should now be tentative (awaiting payment)
        self.assertEqual(order.status, 'tentative')
        self.assertEqual(order.estimated_prep_time_minutes, 20)

    def test_payment_bypass_workflow(self):
        self.client.login(username="cust_order_test", password="testpass")
        
        # Create tentative order
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="waiting",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='tentative'
        )
        
        # Request the sandbox payment bypass URL
        from django.urls import reverse
        response = self.client.get(reverse('restaurants:order_payment_bypass', args=[order.id]))
        
        self.assertEqual(response.status_code, 302)
        
        # Verify order is preparing and token is paid
        order.refresh_from_db()
        token.refresh_from_db()
        
        self.assertEqual(order.status, 'preparing')
        self.assertEqual(token.payment_status, 'paid')

    def test_reject_order_releases_table(self):
        """Verify that rejecting an order releases the previously allocated table."""
        from login.models import User
        staff_user = User.objects.create_superuser(username="staff_rej_test", password="staffpass")
        self.client.login(username="staff_rej_test", password="staffpass")
        
        # Pre-allocate a table
        self.table1.is_occupied = True
        self.table1.save()
        
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="waiting",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='pending_confirmation'
        )
        
        from django.urls import reverse
        self.client.post(reverse('restaurants:reject_order', args=[order.id]), {
            'rejection_reason': 'Too busy',
        })
        
        order.refresh_from_db()
        self.table1.refresh_from_db()
        
        # Order should be cancelled and table should be released
        self.assertEqual(order.status, 'cancelled')
        self.assertFalse(self.table1.is_occupied)

    def test_accept_order_reassigns_table(self):
        """Verify that accepting an order with a new table releases the old one and marks the new one occupied."""
        from login.models import User
        staff_user = User.objects.create_superuser(username="staff_reas_test", password="staffpass")
        self.client.login(username="staff_reas_test", password="staffpass")
        
        # table1 occupied by this order; table2 is vacant
        self.table1.is_occupied = True
        self.table1.save()
        self.table2.is_occupied = False
        self.table2.save()
        
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="waiting",
            user=self.user,
            payment_status='unpaid'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            table=self.table1,
            order_type='dine_in',
            status='pending_confirmation'
        )
        
        from django.urls import reverse
        # Kitchen re-assigns to table2
        self.client.post(reverse('restaurants:accept_order', args=[order.id]), {
            'prep_time': '15',
            'table': self.table2.id,
        })
        
        order.refresh_from_db()
        self.table1.refresh_from_db()
        self.table2.refresh_from_db()
        
        # Order should be tentative and assigned to table2
        self.assertEqual(order.status, 'tentative')
        self.assertEqual(order.table, self.table2)
        # Old table (table1) should be released
        self.assertFalse(self.table1.is_occupied)
        # New table (table2) should be occupied
        self.assertTrue(self.table2.is_occupied)

    def test_checkout_delivery_pay_at_home_urban_branch(self):
        # Enable delivery for this branch
        self.branch.offers_delivery = True
        self.branch.save()

        self.client.login(username="cust_order_test", password="testpass")
        
        # Populate session cart
        session = self.client.session
        session['restaurant_cart'] = {str(self.item.id): 1}
        session['restaurant_cart_branch_id'] = self.branch.id
        session.save()
        
        # Post to checkout view (delivery and pay_at_home)
        from django.urls import reverse
        response = self.client.post(reverse('restaurants:checkout_order'), {
            'order_type': 'delivery',
            'delivery_address': 'My Test Address 123',
            'payment_option': 'pay_at_home',
            'minutes_until_arrival': '30',
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify order and token details
        from restaurants.models import RestaurantOrder
        order = RestaurantOrder.objects.filter(order_type='delivery').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.delivery_address, 'My Test Address 123')
        self.assertEqual(order.token.payment_status, 'pay_at_home')
        self.assertTrue(order.customer_arrived)

    def test_checkout_delivery_rejected_when_not_offered(self):
        # Leave offers_delivery = False (default)
        self.client.login(username="cust_order_test", password="testpass")
        
        # Populate session cart
        session = self.client.session
        session['restaurant_cart'] = {str(self.item.id): 1}
        session['restaurant_cart_branch_id'] = self.branch.id
        session.save()
        
        # Post to checkout view (delivery)
        from django.urls import reverse
        response = self.client.post(reverse('restaurants:checkout_order'), {
            'order_type': 'delivery',
            'delivery_address': 'My Test Address 123',
            'payment_option': 'pay_at_home',
            'minutes_until_arrival': '30',
        })
        
        # Should redirect back to checkout order view due to error redirect
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('restaurants:checkout_order')))

    def test_accept_pay_at_home_delivery_order(self):
        from accounts.models import PlatformFee
        PlatformFee.objects.create(
            fee_logged_in=Decimal('5.50'),
            fee_guest=Decimal('10.00'),
            is_active=True
        )

        # Create a delivery pay_at_home order manually
        from django.utils import timezone
        from queues.models import Token
        from restaurants.models import RestaurantOrder, RestaurantOrderItem
        
        token = Token.objects.create(
            branch=self.branch,
            token_date=timezone.now().date(),
            status="waiting",
            user=self.user,
            payment_status='pay_at_home'
        )
        order = RestaurantOrder.objects.create(
            token=token,
            branch=self.branch,
            order_type='delivery',
            status='pending_confirmation',
            delivery_address='Test Address',
            customer_arrived=True
        )
        RestaurantOrderItem.objects.create(
            order=order,
            menu_item=self.item,
            quantity=2,
            price=self.item.price
        )
        
        # Kitchen accepts order
        from django.urls import reverse
        self.client.login(username="cust_order_test", password="testpass")
        
        response = self.client.post(reverse('restaurants:accept_order', args=[order.id]), {
            'prep_time': '20',
        })
        
        order.refresh_from_db()
        token.refresh_from_db()
        
        # Order should be preparing (bypassing tentative)
        self.assertEqual(order.status, 'preparing')
        self.assertEqual(token.status, 'serving')
        
        # Subtotal = 2 * 200 = 400. Fee = 5.50. Total = 405.50
        self.assertEqual(token.final_price, Decimal('405.50'))
        self.assertEqual(token.booking_fee, Decimal('5.50'))

        # Expected delivery time should be set
        self.assertIsNotNone(order.expected_delivery_time)

    def test_add_to_cart_success_message(self):
        self.client.login(username="cust_order_test", password="testpass")
        from django.urls import reverse
        
        response = self.client.post(reverse('restaurants:add_to_order_cart'), {
            'menu_item_id': self.item.id,
            'quantity': '2',
            'branch_id': self.branch.id,
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f"Added {self.item.name} to cart.")

    def test_toggle_delivery_status_success_as_branch_admin(self):
        from login.models import User, UserProfile
        from django.urls import reverse
        
        # Create branch admin user
        admin_user = User.objects.create_user(username="branch_admin_user", password="adminpass")
        UserProfile.objects.create(user=admin_user, role='branch_admin', branch=self.branch)
        
        self.client.login(username="branch_admin_user", password="adminpass")
        
        self.assertFalse(self.branch.offers_delivery)
        
        # Toggle to True
        response = self.client.post(reverse('restaurants:toggle_delivery_status', args=[self.branch.id]))
        self.assertEqual(response.status_code, 302)
        
        self.branch.refresh_from_db()
        self.assertTrue(self.branch.offers_delivery)
        
        # Toggle back to False
        response = self.client.post(reverse('restaurants:toggle_delivery_status', args=[self.branch.id]))
        self.assertEqual(response.status_code, 302)
        
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.offers_delivery)

    def test_toggle_delivery_status_denied_as_customer(self):
        from django.urls import reverse
        
        self.client.login(username="cust_order_test", password="testpass")
        self.assertFalse(self.branch.offers_delivery)
        
        response = self.client.post(reverse('restaurants:toggle_delivery_status', args=[self.branch.id]))
        self.assertEqual(response.status_code, 302)
        
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.offers_delivery)

    def test_toggle_delivery_status_rejected_for_highway_branch(self):
        from login.models import User
        from restaurants.models import Highway, HighwayBranch
        from django.urls import reverse
        
        # Create superuser to bypass role checking
        superuser = User.objects.create_superuser(username="super_user", password="superpass")
        self.client.login(username="super_user", password="superpass")
        
        # Make the branch a highway branch
        highway = Highway.objects.create(name="NH-44 Test", start_point="A", end_point="B")
        HighwayBranch.objects.create(branch=self.branch, highway=highway, milestone_km=10.5)
        
        self.assertFalse(self.branch.offers_delivery)
        
        response = self.client.post(reverse('restaurants:toggle_delivery_status', args=[self.branch.id]))
        self.assertEqual(response.status_code, 302)
        
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.offers_delivery)


