from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from login.models import User, UserProfile
from organization.models import Branch, Organization, Service_Category


class LoginLandingTests(TestCase):
    """Each kind of user lands on the right page after login."""

    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.org = org
        self.salon = Branch.objects.create(name="Salon", organization=org,
                                           services_category=Service_Category.objects.create(name="Salon"))
        self.rest = Branch.objects.create(name="Dhaba", organization=org,
                                          services_category=Service_Category.objects.create(name="Restaurant"))

    def make(self, username, role=None, branch=None, organization=None, **flags):
        user = User.objects.create_user(username=username, password="pass", **flags)
        if role:
            UserProfile.objects.create(user=user, role=role, branch=branch, organization=organization)
        return user

    def login(self, username, next_url=None):
        url = reverse("user_login") + (f"?next={next_url}" if next_url else "")
        return self.client.post(url, {"username": username, "password": "pass"})

    def assertLands(self, username, expected, next_url=None):
        response = self.login(username, next_url)
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_customer_goes_to_services_page(self):
        self.make("c", "customer")
        self.assertLands("c", reverse("index"))

    def test_owner_goes_to_workspace(self):
        self.make("o", "org_admin", organization=self.org)
        self.assertLands("o", reverse("workspace:home"))

    def test_salon_branch_admin_goes_to_shop_dashboard(self):
        self.make("ba", "branch_admin", branch=self.salon)
        self.assertLands("ba", reverse("shop_dashboard", args=[self.salon.id]))

    def test_restaurant_branch_admin_goes_to_kitchen(self):
        self.make("bar", "branch_admin", branch=self.rest)
        self.assertLands("bar", reverse("restaurants:kitchen_dashboard", args=[self.rest.id]))

    def test_branch_admin_without_branch_goes_to_workspace(self):
        self.make("ban", "branch_admin")
        self.assertLands("ban", reverse("workspace:home"))

    def test_salon_staff_goes_to_shop_dashboard(self):
        self.make("s", "staff", branch=self.salon)
        self.assertLands("s", reverse("shop_dashboard", args=[self.salon.id]))

    def test_restaurant_staff_goes_to_staff_screen(self):
        self.make("sr", "staff", branch=self.rest)
        self.assertLands("sr", reverse("restaurants:staff_dashboard", args=[self.rest.id]))

    def test_superuser_goes_to_admin(self):
        self.make("root", is_superuser=True, is_staff=True)
        self.assertLands("root", reverse("admin:index"))

    def test_next_is_followed(self):
        self.make("c2", "customer")
        self.assertLands("c2", "/workspace/", next_url="/workspace/")

    def test_business_user_ignores_next_to_services_page(self):
        self.make("ba2", "branch_admin", branch=self.salon)
        self.assertLands("ba2", reverse("shop_dashboard", args=[self.salon.id]), next_url="/")


class BrowseWithoutLoginTests(TestCase):
    """Visitors can view shops and menus; login / guest is asked only when adding to the cart."""

    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.salon = Branch.objects.create(name="Salon", organization=org, is_approved=True,
                                           services_category=Service_Category.objects.create(name="Salon"))
        self.rest = Branch.objects.create(name="Dhaba", organization=org, is_approved=True,
                                          services_category=Service_Category.objects.create(name="Restaurant"))

    def test_visitor_can_view_salon_services(self):
        response = self.client.get(reverse("branch_services", args=[self.salon.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Browse freely")

    def test_visitor_can_view_restaurant_menu_and_search(self):
        self.assertEqual(self.client.get(reverse("restaurants:menu_view", args=[self.rest.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("restaurants:restaurant_search")).status_code, 200)

    def test_add_to_cart_asks_login_and_returns_to_same_page(self):
        page = reverse("branch_services", args=[self.salon.id])
        response = self.client.post(reverse("add_to_cart"), {}, HTTP_REFERER=f"http://testserver{page}")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login_choice"), response.url)
        self.assertIn(quote(page, safe=""), response.url)

    def test_add_to_order_cart_asks_login(self):
        response = self.client.post(reverse("restaurants:add_to_order_cart"), {})
        self.assertIn(reverse("login_choice"), response.url)


class CustomerIdleLogoutTests(TestCase):
    """Customers/guests are logged out after 5 idle minutes; business users and active bookings are not."""

    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Salon", organization=org,
                                            services_category=Service_Category.objects.create(name="Salon"))

    def go_idle(self, minutes=6):
        session = self.client.session
        session["last_seen"] = session.get("last_seen", 0) - minutes * 60
        session.save()

    def test_customer_logged_out_after_idle(self):
        user = User.objects.create_user(username="c", password="pass")
        UserProfile.objects.create(user=user, role="customer")
        self.client.login(username="c", password="pass")
        self.client.get(reverse("index"))
        self.go_idle()
        self.client.get(reverse("index"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_customer_with_active_token_stays(self):
        from queues.models import Token
        user = User.objects.create_user(username="c2", password="pass")
        UserProfile.objects.create(user=user, role="customer")
        Token.objects.create(branch=self.branch, user=user, token_number=1, status="waiting")
        self.client.login(username="c2", password="pass")
        self.client.get(reverse("index"))
        self.go_idle()
        self.client.get(reverse("index"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_branch_admin_not_logged_out(self):
        user = User.objects.create_user(username="ba", password="pass")
        UserProfile.objects.create(user=user, role="branch_admin", branch=self.branch)
        self.client.login(username="ba", password="pass")
        self.client.get(reverse("workspace:home"))
        self.go_idle(60)
        self.client.get(reverse("workspace:home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_guest_logged_out_after_idle(self):
        from login.models import Guest
        guest = Guest.objects.create(name="G", email="g@t.com", phone_no="1", pin_code="110001")
        session = self.client.session
        session["guest_id"] = guest.id
        session.save()
        self.client.get(reverse("index"))
        self.go_idle()
        self.client.get(reverse("index"))
        self.assertNotIn("guest_id", self.client.session)
