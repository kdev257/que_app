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
        self.data = {"is_gst_registered": "on", "gstin": "07abcde1234f1z2", "gst_state_code": "07",
                     "gst_percentage": "12", "prices_include_gst": ""}

    def test_branch_admin_can_save(self):
        self.client.login(username="adm", password="pass")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, self.data)
        self.branch.refresh_from_db()
        self.assertTrue(self.branch.is_gst_registered)
        self.assertEqual(self.branch.gstin, "07ABCDE1234F1Z2")
        self.assertEqual(self.branch.state, "Delhi")  # filled from the state code
        self.assertEqual(self.branch.gst_percentage, Decimal("12"))
        self.assertFalse(self.branch.prices_include_gst)

    def test_gstin_required_when_registered(self):
        self.client.login(username="adm", password="pass")
        self.data["gstin"] = ""
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)  # form shown again with error
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.is_gst_registered)

    def test_gstin_must_match_state_and_checksum(self):
        self.client.login(username="adm", password="pass")
        self.data["gst_state_code"] = "27"  # GSTIN starts with 07 (Delhi)
        self.assertContains(self.client.post(self.url, self.data), "belongs to Delhi")
        self.data.update(gst_state_code="07", gstin="07ABCDE1234F1Z5")  # wrong last character
        self.assertContains(self.client.post(self.url, self.data), "typing mistake")
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
        self.assertRegex(invoice.invoice_number, r"^SAL/\d\d-\d\d/00001$")  # GST: max 16 chars, FY series
        self.assertLessEqual(len(invoice.invoice_number), 16)
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


class PlaceOfSupplyTests(TestCase):
    """CGST+SGST / CGST+UTGST / IGST (IGST Act s.12)."""

    def setUp(self):
        from organization.models import Service_Category
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.salon = Service_Category.objects.create(name="Salon", place_of_supply_rule="performed")
        self.tuition = Service_Category.objects.create(name="Tuition", place_of_supply_rule="general")
        self.branch = Branch.objects.create(name="B", organization=org, services_category=self.salon,
                                            is_gst_registered=True, gstin="27ABCDE1234F1Z0", gst_state_code="27",
                                            gst_percentage=Decimal("18"), prices_include_gst=False)

    def amounts(self, customer=None, fee=None, booking_fee="0"):
        return calculate_amounts(Decimal("1000"), Decimal("0"), Decimal(booking_fee), self.branch, fee, customer)

    def test_salon_always_cgst_sgst_even_for_other_state_customer(self):
        a = self.amounts({"gstin": "29ABCDE1234F1ZW", "state_code": "29"})
        self.assertEqual(a["tax_type"], "intra")
        self.assertEqual((a["cgst_amount"], a["sgst_amount"], a["igst_amount"]), (Decimal("90.00"), Decimal("90.00"), 0))
        self.assertEqual(a["place_of_supply_code"], "27")

    def test_general_rule_other_state_customer_pays_igst(self):
        self.branch.services_category = self.tuition
        a = self.amounts({"gstin": "29ABCDE1234F1ZW"})
        self.assertEqual(a["tax_type"], "inter")
        self.assertEqual(a["igst_amount"], Decimal("180.00"))
        self.assertEqual(a["cgst_amount"] + a["sgst_amount"], 0)
        self.assertEqual(a["place_of_supply_name"], "Karnataka")

    def test_general_rule_no_address_uses_branch_state(self):
        self.branch.services_category = self.tuition
        a = self.amounts({})
        self.assertEqual(a["tax_type"], "intra")
        self.assertEqual(a["place_of_supply_code"], "27")

    def test_union_territory_uses_utgst(self):
        self.branch.gst_state_code, self.branch.gstin = "04", "04ABCDE1234F1Z8"  # Chandigarh
        a = self.amounts()
        self.assertEqual(a["tax_type"], "intra_ut")
        self.assertEqual((a["cgst_amount"], a["utgst_amount"], a["sgst_amount"]), (Decimal("90.00"), Decimal("90.00"), 0))

    def test_gst_after_discount(self):
        a = calculate_amounts(Decimal("1000"), Decimal("200"), Decimal("0"), self.branch)
        self.assertEqual(a["taxable_amount"], Decimal("800.00"))
        self.assertEqual(a["gst_amount"], Decimal("144.00"))

    def test_booking_fee_igst_when_customer_in_other_state(self):
        from accounts.models import PlatformFee
        fee = PlatformFee.objects.create(fee_logged_in=Decimal("10"), gst_on_fee=True, fee_gst_percentage=Decimal("18"),
                                         fee_includes_gst=False, platform_state_code="27")
        a = self.amounts({"state_code": "07"}, fee, booking_fee="10")
        self.assertEqual(a["booking_fee_tax_type"], "inter")
        self.assertEqual(a["booking_fee_igst"], Decimal("1.80"))
        self.assertEqual(a["tax_type"], "intra")  # the salon part is still CGST+SGST

    def test_unregistered_branch_has_no_gst(self):
        self.branch.is_gst_registered = False
        a = self.amounts()
        self.assertEqual(a["tax_type"], "none")
        self.assertEqual(a["gst_amount"], 0)
        self.assertEqual(a["place_of_supply_code"], "")

    def test_invoice_shows_igst_line(self):
        from .models import Invoice
        inv = Invoice(tax_type="inter", igst_amount=Decimal("18"))
        self.assertEqual(inv.tax_lines, [("IGST", Decimal("18"))])
        inv = Invoice(tax_type="intra_ut", cgst_amount=Decimal("9"), utgst_amount=Decimal("9"))
        self.assertEqual([label for label, _ in inv.tax_lines], ["CGST", "UTGST"])


class ProfileSecurityTests(TestCase):
    def test_customer_cannot_make_self_branch_admin(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        branch = Branch.objects.create(name="B", organization=org)
        user = User.objects.create_user(username="c", password="pass")
        UserProfile.objects.create(user=user, role="customer", address="x", pin_code="110001")
        self.client.login(username="c", password="pass")
        self.client.post(reverse("user_profile"), {
            "address": "x", "pin_code": "110001", "role": "branch_admin", "branch": branch.id,
            "organization": org.id, "gstin": "", "business_name": "",
        })
        user.user_profile.refresh_from_db()
        self.assertEqual(user.user_profile.role, "customer")
        self.assertIsNone(user.user_profile.branch_id)

    def test_profile_gstin_is_checked(self):
        user = User.objects.create_user(username="c2", password="pass")
        UserProfile.objects.create(user=user, role="customer", address="x", pin_code="110001")
        self.client.login(username="c2", password="pass")
        response = self.client.post(reverse("user_profile"), {"address": "x", "pin_code": "110001", "gstin": "27ABCDE1234F1Z5"})
        self.assertContains(response, "typing mistake")


class InvoiceComplianceTests(TestCase):
    """FY-wise numbering, SAC codes, payment mode and credit notes."""

    def setUp(self):
        from organization.models import Service_Category
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.cat = Service_Category.objects.create(name="Nail Studio", sac_code="999722", default_gst_rate=Decimal("5"),
                                                   itc_allowed=False, place_of_supply_rule="performed")
        self.branch = Branch.objects.create(
            name="Destello Nail Studio", organization=self.org, services_category=self.cat,
            is_gst_registered=True, gstin="27ABCDE1234F1Z0", gst_state_code="27",
            gst_percentage=Decimal("5"), prices_include_gst=False,
        )
        self.service = Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Gel Polish"),
                                              price=Decimal("1000.00"))
        self.admin = User.objects.create_user(username="adm", password="pass")
        UserProfile.objects.create(user=self.admin, role="branch_admin", branch=self.branch)
        self.staff = User.objects.create_user(username="stf", password="pass")
        UserProfile.objects.create(user=self.staff, role="staff", branch=self.branch)

    def make_invoice(self):
        from .services import create_invoice_for_token
        token = Token.objects.create(branch=self.branch, status="completed", token_date=datetime.date.today())
        TokenService.objects.create(token=token, service=self.service, branch=self.branch)
        return create_invoice_for_token(token)

    def test_numbers_are_consecutive_and_short(self):
        first, second = self.make_invoice(), self.make_invoice()
        self.assertTrue(first.invoice_number.startswith("DNS/"))
        self.assertEqual(second.serial_number, first.serial_number + 1)
        self.assertLessEqual(len(second.invoice_number), 16)

    def test_new_series_each_financial_year(self):
        from django.db import transaction
        from .services import next_document_number
        with transaction.atomic():
            a = next_document_number(self.branch, "invoice", datetime.date(2027, 3, 31))
            b = next_document_number(self.branch, "invoice", datetime.date(2027, 4, 1))
        self.assertEqual(a[0], "DNS/26-27/00001")
        self.assertEqual(b[0], "DNS/27-28/00001")

    def test_sac_and_rates_stored(self):
        invoice = self.make_invoice()
        self.assertEqual(invoice.items.get().sac_code, "999722")
        self.assertEqual((invoice.cgst_rate, invoice.sgst_rate), (Decimal("2.50"), Decimal("2.50")))
        self.assertEqual(invoice.gst_amount, Decimal("50.00"))

    def test_staff_sets_payment_mode(self):
        invoice = self.make_invoice()
        self.client.login(username="stf", password="pass")
        self.client.post(reverse("billing:set_payment_mode", args=[invoice.id]), {"payment_mode": "upi"})
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_mode, "upi")

    def test_partial_credit_note_splits_gst(self):
        invoice = self.make_invoice()  # 1000 + 5% = 1050
        self.client.login(username="adm", password="pass")
        self.client.post(reverse("billing:credit_note_create", args=[invoice.id]), {"amount": "525", "reason": "refund"})
        note = invoice.credit_notes.get()
        self.assertRegex(note.number, r"^DNSC/\d\d-\d\d/0001$")
        self.assertLessEqual(len(note.number), 16)
        self.assertEqual((note.taxable_amount, note.gst_amount), (Decimal("500.00"), Decimal("25.00")))
        self.assertEqual((note.cgst_amount, note.sgst_amount), (Decimal("12.50"), Decimal("12.50")))
        invoice.refresh_from_db()
        self.assertEqual(invoice.credited_amount, Decimal("525.00"))
        # Cannot credit more than what is left
        self.client.post(reverse("billing:credit_note_create", args=[invoice.id]), {"amount": "600", "reason": "refund"})
        self.assertEqual(invoice.credit_notes.count(), 1)

    def test_staff_cannot_issue_credit_note(self):
        invoice = self.make_invoice()
        self.client.login(username="stf", password="pass")
        self.client.post(reverse("billing:credit_note_create", args=[invoice.id]), {"amount": "100", "reason": "refund"})
        self.assertFalse(invoice.credit_notes.exists())

    def test_category_defaults(self):
        from organization.gst import category_defaults
        self.assertEqual(category_defaults("Unisex Salon"), ("999721", "5.00", False))
        self.assertEqual(category_defaults("Restaurant")[0], "996331")
        self.assertIsNone(category_defaults("Tuition"))


class GstRateByLawTests(TestCase):
    """Salon/nails/spa/gym: 5% without ITC (compulsory). Restaurant: 5% without ITC, 18% with ITC in a hotel."""

    def setUp(self):
        from organization.models import Service_Category
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.nails = Service_Category.objects.create(name="Nail Studio", sac_code="999722", itc_allowed=False)
        self.food = Service_Category.objects.create(name="Restaurant", sac_code="996331", itc_allowed=False)
        self.owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")

    def save_gst(self, branch, **extra):
        data = {"is_gst_registered": "on", "gst_state_code": "27", "gstin": "27ABCDE1234F1Z0",
                "gst_percentage": "18", "prices_include_gst": "on", "invoice_prefix": ""}
        data.update(extra)
        self.client.post(reverse("branch_gst_settings", args=[branch.id]), data)
        branch.refresh_from_db()
        return branch

    def test_salon_rate_forced_to_5_without_itc(self):
        branch = Branch.objects.create(name="Destello", organization=self.org, services_category=self.nails)
        branch = self.save_gst(branch)  # tried 18%
        self.assertEqual(branch.gst_percentage, Decimal("5.00"))
        self.assertFalse(branch.itc_allowed)

    def test_restaurant_5_or_18_in_hotel(self):
        branch = Branch.objects.create(name="Dhaba", organization=self.org, services_category=self.food)
        branch = self.save_gst(branch)
        self.assertEqual((branch.gst_percentage, branch.itc_allowed), (Decimal("5.00"), False))
        branch = self.save_gst(branch, specified_premises="on", gst_percentage="5")
        self.assertEqual((branch.gst_percentage, branch.itc_allowed), (Decimal("18.00"), True))

    def test_owner_picks_sac_and_rate_follows(self):
        from organization.models import Service_Category
        other = Service_Category.objects.create(name="Wellness")  # no SAC set by QuickQueue
        branch = Branch.objects.create(name="Glow", organization=self.org, services_category=other)
        branch = self.save_gst(branch)  # no SAC yet: owner's 18% is kept
        self.assertEqual(branch.gst_percentage, Decimal("18.00"))
        branch = self.save_gst(branch, sac_choice="999722")  # owner picks Nails / beauty
        self.assertEqual((branch.sac_code, branch.gst_percentage, branch.itc_allowed), ("999722", Decimal("5.00"), False))
        branch = self.save_gst(branch, sac_choice="other", sac_other="998311", gst_percentage="18")
        self.assertEqual((branch.sac_code, branch.gst_percentage), ("998311", Decimal("18.00")))
        self.assertContains(self.client.get(reverse("branch_gst_settings", args=[branch.id])), "998311")

    def test_hotel_box_ignored_for_salon(self):
        branch = Branch.objects.create(name="Destello", organization=self.org, services_category=self.nails)
        branch = self.save_gst(branch, specified_premises="on")
        self.assertEqual((branch.gst_percentage, branch.specified_premises), (Decimal("5.00"), False))
        self.assertContains(self.client.get(reverse("branch_gst_settings", args=[branch.id])), "compulsory")
