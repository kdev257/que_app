import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from login.models import User, UserProfile
from organization.models import Branch, Organization, Service, Service_Category, Service_Name
from privacy.models import ConsentRecord
from queues.models import Token
from restaurants.models import MenuItem
from reviews.models import Review


class BusinessSignupTests(TestCase):
    def test_signup_creates_owner_org_and_consent(self):
        data = {
            "org_name": "Glow Salon", "org_email": "glow@t.com", "org_phone": "999",
            "first_name": "Asha", "last_name": "K", "email": "asha@t.com", "phone": "98765",
            "username": "asha", "password1": "S3cure-pass-123", "password2": "S3cure-pass-123",
            "age_confirm": "on", "accept_notice": "on",
        }
        response = self.client.post(reverse("workspace:signup"), data)
        self.assertRedirects(response, reverse("workspace:branch_add"))
        user = User.objects.get(username="asha")
        self.assertEqual(user.user_profile.role, "org_admin")
        self.assertEqual(user.user_profile.organization.name, "Glow Salon")
        self.assertTrue(ConsentRecord.objects.filter(user=user).exists())


class WorkspaceTests(TestCase):
    def setUp(self):
        self.salon_cat = Service_Category.objects.create(name="Salon")
        self.rest_cat = Service_Category.objects.create(name="Restaurant")
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.other_org = Organization.objects.create(name="Other", email="x@t.com", phone="2")
        self.owner = User.objects.create_user(username="owner", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)
        self.branch = Branch.objects.create(name="Main", organization=self.org, services_category=self.salon_cat,
                                            pin_code="110001", is_approved=True)
        self.other_branch = Branch.objects.create(name="Theirs", organization=self.other_org,
                                                  services_category=self.salon_cat, is_approved=False)

    def test_owner_sees_workspace_link_and_home(self):
        self.client.login(username="owner", password="pass")
        response = self.client.get(reverse("index"))  # business accounts are sent to their workspace
        self.assertRedirects(response, reverse("workspace:home"), fetch_redirect_response=False)
        response = self.client.get(reverse("workspace:home"))
        self.assertContains(response, "Main")
        self.assertNotContains(response, "Theirs")

    def test_owner_adds_branch_pending_approval(self):
        self.client.login(username="owner", password="pass")
        self.client.post(reverse("workspace:branch_add"), {
            "name": "Second", "services_category": self.salon_cat.id, "address": "Road 1", "city": "Delhi",
            "pin_code": "110002", "phone": "123", "number_of_employees": 2,
            "opening_time": "09:00", "closing_time": "20:00",
        })
        branch = Branch.objects.get(name="Second")
        self.assertEqual(branch.organization, self.org)
        self.assertFalse(branch.is_approved)

    def test_add_service_select_or_new_name(self):
        haircut = Service_Name.objects.create(name="Haircut")
        self.client.login(username="owner", password="pass")
        url = reverse("workspace:services", args=[self.branch.id])
        response = self.client.get(url)
        self.assertContains(response, 'name="service_choice"')
        self.assertContains(response, "+ Add a new service name")
        # Select an existing name from the dropdown
        self.client.post(url, {"service_choice": str(haircut.id), "description": "Includes wash", "price": "200",
                               "average_time_minutes": 20, "is_active": "on"})
        # Choose "+ Add new" and type a new name
        self.client.post(url, {"service_choice": "new", "new_service_name": "Beard  trim", "price": "100",
                               "average_time_minutes": 10, "is_active": "on"})
        # "+ Add new" with an empty name is rejected
        response = self.client.post(url, {"service_choice": "new", "new_service_name": "", "price": "50",
                                          "average_time_minutes": 5, "is_active": "on"})
        self.assertContains(response, "Please type the new service name.")
        self.assertEqual(Service_Name.objects.filter(name__iexact="haircut").count(), 1)  # reused, not duplicated
        self.assertTrue(Service_Name.objects.filter(name="Beard Trim").exists())        # new name added
        self.assertEqual(Service.objects.filter(branch=self.branch).count(), 2)
        haircut_svc = Service.objects.get(branch=self.branch, name__name="Haircut")
        self.assertEqual(haircut_svc.price, Decimal("200"))
        self.assertEqual(haircut_svc.description, "Includes wash")

    def test_toggle_hides_service_from_customers(self):
        svc = Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Spa"), price=500)
        self.client.login(username="owner", password="pass")
        self.client.post(reverse("workspace:service_toggle", args=[self.branch.id, svc.id]))
        svc.refresh_from_db()
        self.assertFalse(svc.is_active)

    def test_cannot_manage_other_organization(self):
        self.client.login(username="owner", password="pass")
        self.client.post(reverse("workspace:services", args=[self.other_branch.id]),
                         {"service_choice": "new", "new_service_name": "Hack", "price": "1",
                          "average_time_minutes": 1, "is_active": "on"})
        self.assertFalse(Service.objects.filter(branch=self.other_branch).exists())

    def test_branch_admin_manages_only_own_branch_and_cannot_add_branch(self):
        admin = User.objects.create_user(username="badmin", password="pass")
        UserProfile.objects.create(user=admin, role="branch_admin", branch=self.branch, organization=self.org)
        self.client.login(username="badmin", password="pass")
        self.assertEqual(self.client.get(reverse("workspace:services", args=[self.branch.id])).status_code, 200)
        self.client.post(reverse("workspace:branch_add"), {"name": "Nope", "services_category": self.salon_cat.id})
        self.assertFalse(Branch.objects.filter(name="Nope").exists())

    def test_restaurant_menu_item(self):
        rest = Branch.objects.create(name="Dhaba", organization=self.org, services_category=self.rest_cat)
        self.client.login(username="owner", password="pass")
        self.client.post(reverse("workspace:menu", args=[rest.id]), {
            "category_name": "Starters", "item_name": "Paneer Tikka", "price": "250",
            "preparation_time_minutes": 15, "is_veg": "on", "is_available": "on",
        })
        item = MenuItem.objects.get(category__branch=rest)
        self.assertEqual(item.name.name, "Paneer Tikka")

    def test_owner_cannot_book_at_customer_pages(self):
        self.client.login(username="owner", password="pass")
        response = self.client.get(reverse("branch_services", args=[self.branch.id]))
        self.assertRedirects(response, reverse("workspace:home"), fetch_redirect_response=False)
        staff = User.objects.create_user(username="stf", password="pass")
        UserProfile.objects.create(user=staff, role="staff", branch=self.branch)
        self.client.login(username="stf", password="pass")
        response = self.client.get(reverse("branch_services", args=[self.branch.id]))
        self.assertRedirects(response, reverse("shop_dashboard", args=[self.branch.id]), fetch_redirect_response=False)

    def test_unapproved_branch_hidden_from_customers(self):
        self.client.logout()
        response = self.client.get(reverse("branch_services", args=[self.other_branch.id]))
        self.assertIn(response.status_code, (302, 404))


class ReviewTests(TestCase):
    def setUp(self):
        cat = Service_Category.objects.create(name="Salon")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Main", organization=org, services_category=cat, is_approved=True)
        self.customer = User.objects.create_user(username="cust", password="pass", first_name="Rahul", last_name="Sharma")
        UserProfile.objects.create(user=self.customer, role="customer")
        self.token = Token.objects.create(branch=self.branch, user=self.customer, status="completed")
        self.client.login(username="cust", password="pass")

    def test_rate_completed_visit_updates_branch_average(self):
        self.client.post(reverse("reviews:rate_visit", args=[self.token.id]),
                         {"rating": "4", "tags": ["friendly", "clean"], "comment": "Nice"})
        review = Review.objects.get(token=self.token)
        self.assertEqual(review.display_name, "Rahul S.")
        self.assertEqual(review.tags, "friendly,clean")
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.rating_count, 1)
        self.assertEqual(self.branch.rating_avg, Decimal("4.00"))

        # Editing within 7 days updates, no duplicate
        self.client.post(reverse("reviews:rate_visit", args=[self.token.id]), {"rating": "2"})
        self.assertEqual(Review.objects.count(), 1)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.rating_avg, Decimal("2.00"))

    def test_cannot_rate_waiting_or_others_visit(self):
        waiting = Token.objects.create(branch=self.branch, user=self.customer, status="waiting")
        self.client.post(reverse("reviews:rate_visit", args=[waiting.id]), {"rating": "5"})
        other = User.objects.create_user(username="other", password="pass")
        others_token = Token.objects.create(branch=self.branch, user=other, status="completed")
        self.client.post(reverse("reviews:rate_visit", args=[others_token.id]), {"rating": "1"})
        self.assertFalse(Review.objects.exists())

    def test_edit_window_closes_after_7_days(self):
        self.client.post(reverse("reviews:rate_visit", args=[self.token.id]), {"rating": "5"})
        Review.objects.update(created_at=timezone.now() - datetime.timedelta(days=8))
        self.client.post(reverse("reviews:rate_visit", args=[self.token.id]), {"rating": "1"})
        self.assertEqual(Review.objects.get().rating, 5)

    def test_owner_can_reply(self):
        review = Review.objects.create(token=self.token, branch=self.branch, user=self.customer, rating=3,
                                       display_name="Rahul S.")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.branch.organization)
        self.client.login(username="own", password="pass")
        self.client.post(reverse("workspace:reviews", args=[self.branch.id]), {"review_id": review.id, "reply": "Thanks!"})
        review.refresh_from_db()
        self.assertEqual(review.reply, "Thanks!")


class BranchMatchingTests(TestCase):
    """Customer -> branch matching: same PIN -> nearby PIN -> city -> all, plus search."""

    def setUp(self):
        from login.models import City, State
        from restaurants.models import RestaurantLandmark
        self.cat = Service_Category.objects.create(name="Salon")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        mk = lambda name, pin, city, **kw: Branch.objects.create(
            name=name, organization=org, services_category=self.cat, pin_code=pin, city=city, **kw)
        self.same_pin = mk("Same Pin", "110001", "Delhi")
        self.nearby = mk("Nearby", "110005", "Delhi")
        self.far = mk("Far Away", "400001", "Mumbai", locality="Colaba")
        self.hidden = mk("Not Approved", "110001", "Delhi", is_approved=False)
        RestaurantLandmark.objects.create(branch=self.far, name="Gateway of India")
        state = State.objects.create(name="Maharashtra")
        self.mumbai = City.objects.create(state=state, name="Mumbai")
        self.url = reverse("services_list", args=[self.cat.id])

    def _login(self, pin, city=None):
        user = User.objects.create_user(username=f"u{pin}", password="pass")
        UserProfile.objects.create(user=user, role="customer", pin_code=pin, city=city)
        self.client.login(username=f"u{pin}", password="pass")

    def _names(self, response):
        return [b.name for b in response.context["services"]]

    def test_same_pin_first(self):
        self._login("110001")
        names = self._names(self.client.get(self.url))
        self.assertEqual(names, ["Same Pin"])  # unapproved branch never shown

    def test_nearby_pin_when_no_exact_match(self):
        self._login("110009")
        response = self.client.get(self.url)
        self.assertEqual(sorted(self._names(response)), ["Nearby", "Same Pin"])
        self.assertIn("nearby", response.context["match_note"])

    def test_city_when_no_nearby_pin(self):
        self._login("401000", city=self.mumbai)
        self.assertEqual(self._names(self.client.get(self.url)), ["Far Away"])

    def test_all_when_nothing_near(self):
        self._login("999999")
        self.assertEqual(len(self._names(self.client.get(self.url))), 3)

    def test_search_by_landmark_locality_and_text(self):
        self._login("110001")
        r = self.client.get(self.url, {"criteria": "landmark", "selected_val": "Gateway of India"})
        self.assertEqual(self._names(r), ["Far Away"])
        r = self.client.get(self.url, {"criteria": "locality", "selected_val": "Colaba"})
        self.assertEqual(self._names(r), ["Far Away"])
        r = self.client.get(self.url, {"criteria": "text", "q": "gateway"})
        self.assertEqual(self._names(r), ["Far Away"])

    def test_open_and_better_rated_first(self):
        Branch.objects.filter(pk=self.nearby.pk).update(is_open=True, rating_avg=4.5, rating_count=3)
        self._login("110009")
        self.assertEqual(self._names(self.client.get(self.url))[0], "Nearby")

    def test_branch_admin_sets_landmarks_in_workspace(self):
        admin = User.objects.create_user(username="ba", password="pass")
        UserProfile.objects.create(user=admin, role="branch_admin", branch=self.same_pin)
        self.client.login(username="ba", password="pass")
        self.client.post(reverse("workspace:branch_edit", args=[self.same_pin.id]), {
            "name": "Same Pin", "services_category": self.cat.id, "address": "Road 1", "city": "Delhi",
            "pin_code": "110001", "phone": "123", "number_of_employees": 1,
            "opening_time": "09:00", "closing_time": "20:00",
            "landmarks": "Near City Mall,  Opp. Metro Gate 2, near city mall",
        })
        self.assertEqual(sorted(self.same_pin.landmarks.values_list("name", flat=True)),
                         ["Near City Mall", "Opp. Metro Gate 2"])


class EmailRatingAndSocialTests(TestCase):
    """HTML emails, signed rating/invoice links from the email, branch social links."""

    def setUp(self):
        from login.models import Guest
        cat = Service_Category.objects.create(name="Salon")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Glow", organization=org, services_category=cat, is_approved=True)
        self.guest = Guest.objects.create(name="Neha Gupta", email="neha@t.com", phone_no="99", pin_code="110001")
        self.token = Token.objects.create(branch=self.branch, guest=self.guest, status="completed")
        svc = Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Spa"), price=500)
        from queues.models import TokenService
        TokenService.objects.create(token=self.token, service=svc, branch=self.branch)

    def _invoice(self):
        from billing.services import create_invoice_for_token, send_invoice_email
        invoice = create_invoice_for_token(self.token)
        self.assertTrue(send_invoice_email(invoice))
        return invoice

    def test_invoice_email_is_html_with_rating_link(self):
        from django.core import mail
        self._invoice()
        msg = mail.outbox[0]
        html = msg.alternatives[0][0]
        self.assertIn("Rate your visit", html)
        self.assertIn("/reviews/rate/%d/?k=" % self.token.id, html)
        self.assertIn("/reviews/rate/%d/?k=" % self.token.id, msg.body)  # plain-text copy too

    def test_guest_can_rate_from_email_link_without_login(self):
        import re
        from django.core import mail
        self._invoice()
        link = re.search(r"(/reviews/rate/\d+/\?k=[^\s\"<]+)", mail.outbox[0].body).group(1)
        self.client.post(link, {"rating": "5", "comment": "Lovely"})
        review = Review.objects.get(token=self.token)
        self.assertEqual(review.guest, self.guest)
        self.assertEqual(review.display_name, "Neha G.")

    def test_bad_rating_key_is_refused(self):
        url = reverse("reviews:rate_visit", args=[self.token.id]) + "?k=fake"
        self.client.post(url, {"rating": "1"})
        self.assertFalse(Review.objects.exists())

    def test_invoice_link_from_email_opens_without_login(self):
        import re
        from django.core import mail
        invoice = self._invoice()
        link = re.search(r"(/billing/invoice/\d+/\?k=[^\s\"<]+)", mail.outbox[0].body).group(1)
        response = self.client.get(link)
        self.assertContains(response, invoice.invoice_number)
        self.assertEqual(self.client.get(reverse("billing:invoice_detail", args=[invoice.id])).status_code, 302)

    def test_privacy_email_is_html(self):
        from django.core import mail
        from privacy.services import _send
        _send("Test - QuickQueue", "Hi Neha,\n\nYour request is received.", "neha@t.com")
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        self.assertIn("Your request is received.", mail.outbox[0].alternatives[0][0])

    def test_whatsapp_link_and_social_icons(self):
        self.branch.whatsapp_number = "98765 43210"
        self.branch.instagram_url = "https://instagram.com/glow"
        self.branch.save()
        self.assertEqual(self.branch.whatsapp_link, "https://wa.me/919876543210")
        response = self.client.get(reverse("reviews:branch_reviews", args=[self.branch.id]))
        self.assertContains(response, "https://instagram.com/glow")
        self.assertContains(response, "https://wa.me/919876543210")
        self.assertContains(response, "Copy link")


class ServiceIconTests(TestCase):
    def test_icon_and_colour_picked_from_name_and_stored(self):
        cases = {"Hair Cut": ("bi-scissors", "hair"), "Beard Trim": ("bi-scissors", "grooming"),
                 "Gold Facial": ("bi-stars", "skin"), "Pedicure": ("bi-hand-index-thumb", "nails"),
                 "Aroma Massage": ("bi-flower1", "spa"), "Bridal Makeup": ("bi-brush", "makeup"),
                 "Something Else": ("bi-bookmark-star", "other")}
        for name, (icon, group) in cases.items():
            sn = Service_Name.objects.create(name=name)
            self.assertEqual((sn.icon, sn.icon_group), (icon, group), name)

    def test_admin_choice_is_kept(self):
        sn = Service_Name.objects.create(name="Haircut", icon="bi-star", icon_group="spa")
        sn.refresh_from_db()
        self.assertEqual((sn.icon, sn.icon_group), ("bi-star", "spa"))

    def test_rate_card_shows_coloured_icons(self):
        cat = Service_Category.objects.create(name="Salon")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=org)
        branch = Branch.objects.create(name="B", organization=org, services_category=cat)
        Service.objects.create(branch=branch, name=Service_Name.objects.create(name="Body Massage"), price=800)
        self.client.login(username="own", password="pass")
        response = self.client.get(reverse("workspace:services", args=[branch.id]))
        self.assertContains(response, "svc-tile svc-spa")
        self.assertContains(response, "bi-flower1")
        self.assertContains(response, "1 live for customers")


class QrPosterTests(TestCase):
    def setUp(self):
        self.salon_cat = Service_Category.objects.create(name="Salon")
        self.rest_cat = Service_Category.objects.create(name="Restaurant")
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Glow", organization=self.org, services_category=self.salon_cat)
        self.staff = User.objects.create_user(username="stf", password="pass")
        UserProfile.objects.create(user=self.staff, role="staff", branch=self.branch)

    def test_staff_gets_poster_with_branch_link(self):
        self.client.login(username="stf", password="pass")
        response = self.client.get(reverse("workspace:qr_poster", args=[self.branch.id]))
        self.assertContains(response, "Scan to join the queue")
        self.assertContains(response, reverse("branch_services", args=[self.branch.id]) + "?src=qr")

    def test_restaurant_poster_links_to_menu(self):
        rest = Branch.objects.create(name="Dhaba", organization=self.org, services_category=self.rest_cat)
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        response = self.client.get(reverse("workspace:qr_poster", args=[rest.id]))
        self.assertContains(response, "Scan to order")
        self.assertContains(response, reverse("restaurants:menu_view", args=[rest.id]) + "?src=qr")

    def test_customer_cannot_open_poster(self):
        customer = User.objects.create_user(username="cust", password="pass")
        UserProfile.objects.create(user=customer, role="customer")
        self.client.login(username="cust", password="pass")
        response = self.client.get(reverse("workspace:qr_poster", args=[self.branch.id]))
        self.assertEqual(response.status_code, 302)


class TableQrTests(TestCase):
    """Table QR codes: add tables, print cards, scan -> menu remembers table -> checkout pre-selects it."""

    def setUp(self):
        from restaurants.models import GlobalMenuItem, MenuCategory, MenuCategoryName, MenuItem, Table
        cat = Service_Category.objects.create(name="Restaurant")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.rest = Branch.objects.create(name="Dhaba", organization=org, services_category=cat, is_approved=True)
        self.other = Branch.objects.create(name="Other", organization=org, services_category=cat, is_approved=True)
        self.admin = User.objects.create_user(username="ba", password="pass")
        UserProfile.objects.create(user=self.admin, role="branch_admin", branch=self.rest)
        self.customer = User.objects.create_user(username="cust", password="pass")
        UserProfile.objects.create(user=self.customer, role="customer", pin_code="110001")
        self.t5 = Table.objects.create(branch=self.rest, table_number="5", capacity=4, is_occupied=True)
        self.other_table = Table.objects.create(branch=self.other, table_number="9", capacity=2)
        mc = MenuCategory.objects.create(branch=self.rest, name=MenuCategoryName.objects.create(name="Mains"))
        self.item = MenuItem.objects.create(category=mc, name=GlobalMenuItem.objects.create(name="Dal"), price=150)

    def test_branch_admin_adds_and_switches_off_table(self):
        from restaurants.models import Table
        self.client.login(username="ba", password="pass")
        url = reverse("restaurants:manage_tables", args=[self.rest.id])
        self.client.post(url, {"action": "add", "table_number": "Garden 2", "capacity": "6"})
        self.assertTrue(Table.objects.filter(branch=self.rest, table_number="Garden 2", capacity=6).exists())
        self.client.post(url, {"action": "add", "table_number": "garden 2", "capacity": "2"})  # duplicate
        self.assertEqual(Table.objects.filter(branch=self.rest, table_number__iexact="garden 2").count(), 1)
        self.client.post(url, {"action": "toggle_active", "table_id": self.t5.id})
        self.t5.refresh_from_db()
        self.assertFalse(self.t5.is_active)

    def test_table_qr_sheet_has_one_link_per_table(self):
        self.client.login(username="ba", password="pass")
        response = self.client.get(reverse("workspace:table_qr_sheet", args=[self.rest.id]))
        self.assertContains(response, f"?table={self.t5.id}&amp;src=table_qr")
        self.assertNotContains(response, f"?table={self.other_table.id}&")

    def test_scan_remembers_table_and_checkout_preselects_it(self):
        self.client.login(username="cust", password="pass")
        menu = self.client.get(reverse("restaurants:menu_view", args=[self.rest.id]), {"table": self.t5.id})
        self.assertContains(menu, "Ordering for Table 5")
        session = self.client.session
        session["restaurant_cart"] = {str(self.item.id): 1}
        session["restaurant_cart_branch_id"] = self.rest.id
        session.save()
        checkout = self.client.get(reverse("restaurants:checkout_order"))
        self.assertContains(checkout, "You scanned <b>Table 5</b>")
        self.assertContains(checkout, f'<option value="{self.t5.id}" selected>')  # offered even though occupied

    def _scan_and_order(self, table_payment):
        from restaurants.models import RestaurantOrder
        self.client.login(username="cust", password="pass")
        self.client.get(reverse("restaurants:menu_view", args=[self.rest.id]), {"table": self.t5.id})
        session = self.client.session
        session["restaurant_cart"] = {str(self.item.id): 2}
        session["restaurant_cart_branch_id"] = self.rest.id
        session.save()
        self.client.post(reverse("restaurants:checkout_order"), {
            "order_type": "dine_in", "table": self.t5.id, "table_payment": table_payment,
        })
        return RestaurantOrder.objects.get(branch=self.rest)

    def test_qr_order_pay_later_goes_straight_to_kitchen(self):
        order = self._scan_and_order("pay_later")
        self.assertEqual(order.status, "preparing")  # no kitchen Accept step
        self.assertTrue(order.customer_arrived)
        self.assertEqual(order.table, self.t5)
        self.assertEqual(order.token.payment_status, "pay_at_shop")
        self.assertEqual(order.token.status, "in_progress")
        self.assertEqual(order.token.final_price, 300)  # stored for staff to collect

        self.client.login(username="ba", password="pass")
        order.status = "served"
        order.save()
        staff = self.client.get(reverse("restaurants:staff_dashboard", args=[self.rest.id]))
        self.assertContains(staff, "Collect bill at table")
        self.client.get(reverse("restaurants:staff_mark_completed", args=[order.id]))
        order.token.refresh_from_db()
        self.assertEqual(order.token.payment_status, "paid")

    def test_qr_order_pay_online_skips_accept_and_asks_payment(self):
        order = self._scan_and_order("online")
        self.assertEqual(order.status, "tentative")  # payment page next, then kitchen cooks
        self.assertEqual(order.token.payment_status, "unpaid")
        status = self.client.get(reverse("restaurants:order_status", args=[order.id]))
        self.assertRedirects(status, reverse("restaurants:order_payment", args=[order.id]), fetch_redirect_response=False)

    def test_table_from_another_restaurant_is_ignored(self):
        self.client.login(username="cust", password="pass")
        menu = self.client.get(reverse("restaurants:menu_view", args=[self.rest.id]), {"table": self.other_table.id})
        self.assertNotContains(menu, "Ordering for Table")
