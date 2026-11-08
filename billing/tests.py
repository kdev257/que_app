import datetime
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from login.models import User, UserProfile
from organization.models import Branch, Organization, Service, Service_Name
from queues.models import Token, TokenService
from .models import Invoice
from .services import calculate_amounts


class GstCalculationTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="B", organization=org)

    def test_no_gst_when_not_registered(self):
        a = calculate_amounts(Decimal("500"), Decimal("50"), Decimal("10"), self.branch)
        self.assertEqual(a["gst_amount"], Decimal("0.00"))
        self.assertEqual(a["total_amount"], Decimal("460.00"))

    def test_gst_included_in_price(self):
        self.branch.is_gst_registered = True
        self.branch.gst_percentage = Decimal("18")
        self.branch.prices_include_gst = True
        a = calculate_amounts(Decimal("118"), Decimal("0"), Decimal("0"), self.branch)
        self.assertEqual(a["taxable_amount"], Decimal("100.00"))
        self.assertEqual(a["gst_amount"], Decimal("18.00"))
        self.assertEqual(a["cgst_amount"] + a["sgst_amount"], Decimal("18.00"))
        self.assertEqual(a["total_amount"], Decimal("118.00"))  # total does not change

    def test_gst_added_on_top(self):
        self.branch.is_gst_registered = True
        self.branch.gst_percentage = Decimal("18")
        self.branch.prices_include_gst = False
        a = calculate_amounts(Decimal("100"), Decimal("0"), Decimal("5"), self.branch)
        self.assertEqual(a["gst_amount"], Decimal("18.00"))
        self.assertEqual(a["total_amount"], Decimal("123.00"))


class FeeGstTests(TestCase):
    def setUp(self):
        from accounts.models import PlatformFee
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="B", organization=org)
        self.fee = PlatformFee(fee_logged_in=Decimal("11.80"), gst_on_fee=True,
                               fee_gst_percentage=Decimal("18"), fee_includes_gst=True)

    def test_fee_gst_included(self):
        a = calculate_amounts(Decimal("100"), Decimal("0"), Decimal("11.80"), self.branch, self.fee)
        self.assertEqual(a["booking_fee"], Decimal("10.00"))
        self.assertEqual(a["booking_fee_gst_amount"], Decimal("1.80"))
        self.assertEqual(a["total_amount"], Decimal("111.80"))  # total unchanged

    def test_fee_gst_added_on_top(self):
        self.fee.fee_includes_gst = False
        a = calculate_amounts(Decimal("100"), Decimal("0"), Decimal("10"), self.branch, self.fee)
        self.assertEqual(a["booking_fee_gst_amount"], Decimal("1.80"))
        self.assertEqual(a["total_amount"], Decimal("111.80"))

    def test_no_fee_gst_when_switched_off(self):
        self.fee.gst_on_fee = False
        a = calculate_amounts(Decimal("100"), Decimal("0"), Decimal("10"), self.branch, self.fee)
        self.assertEqual(a["booking_fee_gst_amount"], Decimal("0.00"))
        self.assertEqual(a["total_amount"], Decimal("110.00"))


class BranchGstSettingsPageTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="B", organization=org)
        self.admin = User.objects.create_user(username="adm", password="pass")
        UserProfile.objects.create(user=self.admin, role="branch_admin", branch=self.branch)
        self.staff = User.objects.create_user(username="stf", password="pass")
        UserProfile.objects.create(user=self.staff, role="staff", branch=self.branch)
        self.url = reverse("branch_gst_settings", args=[self.branch.id])
        self.data = {"is_gst_registered": "on", "gstin": "07abcde1234f1z5",
                     "gst_percentage": "12", "prices_include_gst": ""}

    def test_branch_admin_can_save(self):
        self.client.login(username="adm", password="pass")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, self.data)
        self.branch.refresh_from_db()
        self.assertTrue(self.branch.is_gst_registered)
        self.assertEqual(self.branch.gstin, "07ABCDE1234F1Z5")
        self.assertEqual(self.branch.gst_percentage, Decimal("12"))
        self.assertFalse(self.branch.prices_include_gst)

    def test_gstin_required_when_registered(self):
        self.client.login(username="adm", password="pass")
        self.data["gstin"] = ""
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)  # form shown again with error
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.is_gst_registered)

    def test_staff_cannot_change_gst(self):
        self.client.login(username="stf", password="pass")
        self.client.post(self.url, self.data)
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.is_gst_registered)


class InvoiceFlowTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(
            name="Salon", organization=self.org, number_of_employees=1,
            is_gst_registered=True, gstin="07ABCDE1234F1Z5", gst_percentage=Decimal("18"),
        )
        self.other_branch = Branch.objects.create(name="Other", organization=self.org)
        svc_name = Service_Name.objects.create(name="Haircut")
        self.service = Service.objects.create(branch=self.branch, name=svc_name, price=Decimal("236.00"))

        self.staff = User.objects.create_user(username="staff", password="pass")
        UserProfile.objects.create(user=self.staff, role="staff", branch=self.branch, organization=self.org)
        self.other_staff = User.objects.create_user(username="other", password="pass")
        UserProfile.objects.create(user=self.other_staff, role="staff", branch=self.other_branch, organization=self.org)
        self.customer = User.objects.create_user(username="cust", password="pass", email="cust@t.com")
        UserProfile.objects.create(user=self.customer, role="customer")

        self.token = Token.objects.create(
            branch=self.branch, user=self.customer, status="in_progress",
            token_date=datetime.date.today(), start_time=timezone.now(),
            expected_service_time=20,
        )
        TokenService.objects.create(token=self.token, service=self.service, branch=self.branch)

    def test_generate_invoice_creates_and_emails_invoice(self):
        self.client.login(username="staff", password="pass")
        response = self.client.get(reverse("end_service", args=[self.token.id]))

        invoice = Invoice.objects.get(token=self.token)
        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        self.token.refresh_from_db()
        self.assertEqual(self.token.status, "completed")
        self.assertTrue(invoice.is_gst_invoice)
        self.assertEqual(invoice.subtotal, Decimal("236.00"))
        self.assertEqual(invoice.gst_amount, Decimal("36.00"))
        self.assertEqual(invoice.items.count(), 1)
        self.assertTrue(invoice.invoice_number.startswith(f"INV-{self.branch.id}-"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(Invoice.objects.get(pk=invoice.pk).email_sent)

    def test_staff_of_other_branch_cannot_generate_invoice(self):
        self.client.login(username="other", password="pass")
        self.client.get(reverse("end_service", args=[self.token.id]))
        self.token.refresh_from_db()
        self.assertEqual(self.token.status, "in_progress")
        self.assertFalse(Invoice.objects.exists())

    def test_customer_can_view_own_invoice_but_not_others(self):
        self.client.login(username="staff", password="pass")
        self.client.get(reverse("end_service", args=[self.token.id]))
        invoice = Invoice.objects.get(token=self.token)

        self.client.login(username="cust", password="pass")
        response = self.client.get(reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)

        self.client.login(username="other", password="pass")
        response = self.client.get(reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(response.status_code, 302)


class SecurityAndNumberingTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch_a = Branch.objects.create(name="A", organization=org)
        self.branch_b = Branch.objects.create(name="B", organization=org)
        self.customer = User.objects.create_user(username="cust", password="pass")
        UserProfile.objects.create(user=self.customer, role="customer")
        self.intruder = User.objects.create_user(username="intruder", password="pass")
        UserProfile.objects.create(user=self.intruder, role="customer")

    def test_token_numbers_are_per_branch(self):
        today = datetime.date.today()
        a1 = Token.objects.create(branch=self.branch_a, token_date=today)
        a2 = Token.objects.create(branch=self.branch_a, token_date=today)
        b1 = Token.objects.create(branch=self.branch_b, token_date=today)
        self.assertEqual((a1.token_number, a2.token_number, b1.token_number), (1, 2, 1))

    def test_customer_cannot_start_service(self):
        token = Token.objects.create(branch=self.branch_a, user=self.customer)
        self.client.login(username="cust", password="pass")
        self.client.get(reverse("start_service", args=[token.id]))
        token.refresh_from_db()
        self.assertEqual(token.status, "waiting")

    def test_customer_cannot_close_branch(self):
        self.branch_a.is_open = True
        self.branch_a.save()
        self.client.login(username="cust", password="pass")
        self.client.get(reverse("close_branch", args=[self.branch_a.id]))
        self.branch_a.refresh_from_db()
        self.assertTrue(self.branch_a.is_open)

    def test_open_branch_url_works(self):
        admin = User.objects.create_user(username="adm", password="pass")
        UserProfile.objects.create(user=admin, role="branch_admin", branch=self.branch_a)
        self.client.login(username="adm", password="pass")
        response = self.client.get(reverse("open_branch", args=[self.branch_a.id]))
        self.assertEqual(response.status_code, 302)
        self.branch_a.refresh_from_db()
        self.assertTrue(self.branch_a.is_open)

    def test_other_user_cannot_delete_or_cancel_token(self):
        token = Token.objects.create(branch=self.branch_a, user=self.customer)
        self.client.login(username="intruder", password="pass")
        self.client.get(reverse("delete_token", args=[token.id]))
        self.client.get(reverse("cancel_token", args=[token.id]))
        token.refresh_from_db()
        self.assertEqual(token.status, "waiting")

    def test_landing_page_is_services_page_and_choice_on_category(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/customer_dashboard.html")

        from organization.models import Service_Category
        cat = Service_Category.objects.create(name="Grooming")
        response = self.client.get(reverse("services_list", args=[cat.id]))
        self.assertEqual(response.status_code, 200)  # browsing is open; login is asked at "Add to cart"
