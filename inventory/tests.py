import datetime
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from login.models import User, UserProfile
from organization.models import Branch, Organization, Service_Category

from .models import (Item, ItemCategory, ItemName, Receipt, StockBalance, StockCount, StockMove, Supplier,
                     SupplierDirectory)
from .services import line_amounts


class StockTests(TestCase):
    def setUp(self):
        cat = Service_Category.objects.create(name="Nails")
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, services_category=cat,
                                            address="x", itc_allowed=False)
        self.owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        self.supplier = Supplier.objects.create(organization=self.org, name="Beauty Mart", gstin="06ABCDE1234F1Z4")
        self.gel = Item.objects.create(organization=self.org, name="Gel polish", unit="bottle", min_stock=D("5"))

    def post_bill(self, number, qty, rate, gst="18", include=False):
        data = {"supplier": self.supplier.id, "bill_number": number, "bill_date": datetime.date.today().isoformat(),
                "notes": "", "lines-TOTAL_FORMS": "2", "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "1000",
                "lines-0-item": self.gel.id, "lines-0-quantity": qty, "lines-0-rate": rate, "lines-0-gst_rate": gst,
                "lines-1-item": "", "lines-1-quantity": "", "lines-1-rate": "", "lines-1-gst_rate": "18"}
        if include:
            data["rates_include_gst"] = "on"
        return self.client.post(reverse("inventory:receipt_new", args=[self.branch.id]), data)

    def test_line_amounts_with_and_without_itc(self):
        self.assertEqual(line_amounts(D("10"), D("100"), D("18"), False, False), (D("1000.00"), D("180.00"), D("1180.00"), D("1180.00")))
        self.assertEqual(line_amounts(D("10"), D("100"), D("18"), False, True)[3], D("1000.00"))
        self.assertEqual(line_amounts(D("1"), D("118"), D("18"), True, False)[:2], (D("100.00"), D("18.00")))

    def test_receipt_adds_stock_at_cost_including_gst_when_no_itc(self):
        response = self.post_bill("B-1", "10", "100")
        receipt = Receipt.objects.get(bill_number="B-1")
        self.assertRedirects(response, reverse("inventory:receipt_detail", args=[self.branch.id, receipt.id]))
        self.assertFalse(receipt.itc_claimable)
        self.assertEqual((receipt.taxable_amount, receipt.gst_amount, receipt.total_amount, receipt.stock_value),
                         (D("1000.00"), D("180.00"), D("1180.00"), D("1180.00")))
        bal = StockBalance.objects.get(branch=self.branch, item=self.gel)
        self.assertEqual((bal.quantity, bal.value, bal.avg_cost), (D("10"), D("1180.00"), D("118.0000")))
        self.assertFalse(bal.is_low)
        self.assertEqual(StockMove.objects.get().kind, "receipt")

    def test_weighted_average_cost(self):
        self.post_bill("B-1", "10", "100", gst="0")
        self.post_bill("B-2", "10", "200", gst="0")
        bal = StockBalance.objects.get(branch=self.branch, item=self.gel)
        self.assertEqual((bal.quantity, bal.value, bal.avg_cost), (D("20"), D("3000.00"), D("150.0000")))

    def test_itc_branch_keeps_gst_out_of_cost(self):
        self.branch.itc_allowed, self.branch.is_gst_registered = True, True
        self.branch.save()
        self.post_bill("B-1", "10", "100")
        self.assertTrue(Receipt.objects.get().itc_claimable)
        self.assertEqual(StockBalance.objects.get().value, D("1000.00"))

    def test_duplicate_bill_blocked(self):
        self.post_bill("B-1", "1", "100")
        self.post_bill("b-1", "1", "100")
        self.assertEqual(Receipt.objects.count(), 1)

    def test_low_stock_flag(self):
        self.post_bill("B-1", "3", "100")
        self.assertTrue(StockBalance.objects.get().is_low)
        self.assertContains(self.client.get(reverse("inventory:stock", args=[self.branch.id])), "Low")

    def test_supplier_gstin_checked_and_other_org_blocked(self):
        self.client.post(reverse("inventory:suppliers", args=[self.branch.id]), {"name": "Bad", "gstin": "06ABCDE1234F1Z5"})
        self.assertFalse(Supplier.objects.filter(name="Bad").exists())
        org2 = Organization.objects.create(name="Org2", email="z@t.com", phone="2")
        other = User.objects.create_user(username="x", password="pass")
        UserProfile.objects.create(user=other, role="org_admin", organization=org2)
        self.client.login(username="x", password="pass")
        self.assertEqual(self.client.get(reverse("inventory:stock", args=[self.branch.id])).status_code, 302)


class AddItemDropdownTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        self.url = reverse("inventory:stock", args=[self.branch.id])

    def test_pick_existing_name(self):
        acetone = ItemName.objects.create(name="Acetone 500 ml", unit="bottle", category="Nail products")
        self.client.post(self.url, {"item_choice": acetone.id, "unit": "bottle", "category": "Nail products", "min_stock": "2"})
        item = Item.objects.get(organization=self.org)
        self.assertEqual((item.name, item.master), ("Acetone 500 ml", acetone))
        # Already added -> not offered again in the dropdown
        self.assertNotContains(self.client.get(self.url), f'<option value="{acetone.id}"')

    def test_add_new_name_saved_to_common_list(self):
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "  Cuticle   oil ", "unit": "ml",
                                    "category": "", "min_stock": "0"})
        self.assertTrue(ItemName.objects.filter(name="Cuticle oil").exists())
        self.assertEqual(Item.objects.get(organization=self.org).master.name, "Cuticle oil")

    def test_new_name_required_and_no_duplicates(self):
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "", "unit": "ml", "min_stock": "0"})
        self.assertFalse(Item.objects.exists())
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "Gloves", "unit": "box", "min_stock": "0"})
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "gloves", "unit": "box", "min_stock": "0"})
        self.assertEqual(Item.objects.filter(organization=self.org).count(), 1)


    def test_category_pick_and_add_new(self):
        self.assertTrue(ItemCategory.objects.filter(name="Nail products").exists())  # example categories are ready
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "Nail glue", "unit": "tube",
                                    "category_choice": "Nail products", "min_stock": "0"})
        self.assertEqual(Item.objects.get(name="Nail glue").category, "Nail products")
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "Rhinestones", "unit": "pack",
                                    "category_choice": "__newcat__", "new_category": "Nail  art", "min_stock": "0"})
        self.assertTrue(ItemCategory.objects.filter(name="Nail art").exists())
        self.assertEqual(Item.objects.get(name="Rhinestones").category, "Nail art")
        self.assertContains(self.client.get(self.url), "Nail art")



class BusinessTypeFilterTests(TestCase):
    """A salon does not see restaurant item names or categories, and vice versa."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.salon = Branch.objects.create(name="Destello", organization=self.org, address="x", sac_code="999722")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        self.url = reverse("inventory:stock", args=[self.salon.id])
        self.rice = ItemName.objects.create(name="Basmati rice", unit="kg", business_type="food")
        self.gel = ItemName.objects.create(name="Gel base coat", unit="bottle", business_type="beauty")
        self.gloves = ItemName.objects.create(name="Gloves", unit="box", business_type="general")

    def test_salon_sees_beauty_and_common_only(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Gel base coat")
        self.assertContains(page, "Gloves")
        self.assertContains(page, "Nail products")
        self.assertNotContains(page, "Basmati rice")
        self.assertNotContains(page, "Spices &amp; masala")

    def test_salon_cannot_post_restaurant_item(self):
        self.client.post(self.url, {"item_choice": self.rice.id, "unit": "kg", "min_stock": "0"})
        self.assertFalse(Item.objects.exists())

    def test_new_name_gets_branch_type(self):
        self.client.post(self.url, {"item_choice": "__new__", "new_item_name": "Nail wipes", "unit": "pack",
                                    "category_choice": "__newcat__", "new_category": "Nail prep", "min_stock": "0"})
        self.assertEqual(ItemName.objects.get(name="Nail wipes").business_type, "beauty")
        self.assertEqual(ItemCategory.objects.get(name="Nail prep").business_type, "beauty")



class SharedSupplierTests(TestCase):
    """Pick a shared supplier (own editable copy) or add a new one (business details shared)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x", city="Gurgaon",
                                            sac_code="999722")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        self.url = reverse("inventory:suppliers", args=[self.branch.id])
        self.mart = SupplierDirectory.objects.create(name="Beauty Mart", city="Gurgaon", phone="999", business_type="beauty")
        SupplierDirectory.objects.create(name="Veg Wholesale", city="Gurgaon", business_type="food")
        SupplierDirectory.objects.create(name="Delhi Nails Co", city="Delhi", business_type="beauty")

    def test_dropdown_same_type_and_city_only(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Beauty Mart")
        self.assertNotContains(page, "Veg Wholesale")
        self.assertNotContains(page, "Delhi Nails Co")

    def test_pick_shared_makes_own_editable_copy(self):
        self.client.post(self.url, {"supplier_choice": self.mart.id, "name": "Beauty Mart", "phone": "888",
                                    "contact_person": "Ravi", "city": "Gurgaon"})
        copy = Supplier.objects.get(organization=self.org)
        self.assertEqual((copy.directory, copy.phone, copy.contact_person), (self.mart, "888", "Ravi"))
        self.mart.refresh_from_db()
        self.assertEqual(self.mart.phone, "999")  # shared entry unchanged
        self.assertNotContains(self.client.get(self.url), f'<option value="{self.mart.id}"')  # not offered again

    def test_new_supplier_shared_without_contact_person(self):
        self.client.post(self.url, {"supplier_choice": "__new__", "name": "Nail Hub", "contact_person": "Seema",
                                    "phone": "777", "city": "Gurgaon", "items_supplied": "Gel, acrylic"})
        entry = SupplierDirectory.objects.get(name="Nail Hub")
        self.assertEqual((entry.business_type, entry.city, entry.phone), ("beauty", "Gurgaon", "777"))
        self.assertFalse(hasattr(entry, "contact_person"))
        self.assertEqual(Supplier.objects.get(name="Nail Hub").directory, entry)

    def test_must_choose(self):
        self.client.post(self.url, {"name": "X", "city": "Gurgaon"})
        self.assertFalse(Supplier.objects.exists())


class ClosingStockTests(TestCase):
    """Closing stock as at a date: items used = book - counted, at average cost."""

    def setUp(self):
        from .services import post_receipt
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x")
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        supplier = Supplier.objects.create(organization=self.org, name="Mart")
        self.gel = Item.objects.create(organization=self.org, name="Gel", unit="bottle")
        self.day1 = datetime.date.today() - datetime.timedelta(days=10)
        post_receipt(Receipt(branch=self.branch, supplier=supplier, bill_number="1", bill_date=self.day1),
                     [{"item": self.gel, "quantity": D("10"), "rate": D("100"), "gst_rate": D("0")}])
        self.url = reverse("inventory:stock_count_new", args=[self.branch.id])

    def test_count_works_out_items_used(self):
        as_at = (self.day1 + datetime.timedelta(days=5)).isoformat()
        page = self.client.get(self.url, {"as_at": as_at})
        self.assertContains(page, "10 bottle")  # book stock as at the date
        self.client.post(self.url, {"as_at": as_at, f"count_{self.gel.id}": "4"})
        count = StockCount.objects.get(branch=self.branch)
        line = count.lines.get()
        self.assertEqual((line.book_qty, line.counted_qty, line.used_qty), (D("10"), D("4"), D("6")))
        self.assertEqual((count.closing_value, count.used_value), (D("400.00"), D("600.00")))
        bal = StockBalance.objects.get(branch=self.branch, item=self.gel)
        self.assertEqual((bal.quantity, bal.value), (D("4"), D("400.00")))
        self.assertEqual(StockMove.objects.filter(kind="issue").get().quantity, D("-6"))

    def test_book_stock_respects_date(self):
        before = (self.day1 - datetime.timedelta(days=1)).isoformat()
        self.client.post(self.url, {"as_at": before, f"count_{self.gel.id}": "0"})
        line = StockCount.objects.get().lines.get()
        self.assertEqual(line.book_qty, D("0"))  # purchase came after this date

    def test_no_future_or_older_than_last_count(self):
        future = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.client.post(self.url, {"as_at": future, f"count_{self.gel.id}": "4"})
        self.assertFalse(StockCount.objects.exists())
        today = datetime.date.today().isoformat()
        self.client.post(self.url, {"as_at": today, f"count_{self.gel.id}": "8"})
        self.client.post(self.url, {"as_at": self.day1.isoformat(), f"count_{self.gel.id}": "2"})
        self.assertEqual(StockCount.objects.count(), 1)

    def test_negative_count_rejected(self):
        self.client.post(self.url, {"as_at": datetime.date.today().isoformat(), f"count_{self.gel.id}": "-1"})
        self.assertFalse(StockCount.objects.exists())



class StaffCountApprovalTests(TestCase):
    """Staff count quantities only; branch admin reviews, corrects, approves or sends back."""

    def setUp(self):
        from .services import post_receipt
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x")
        self.admin = User.objects.create_user(username="adm", password="pass")
        UserProfile.objects.create(user=self.admin, role="branch_admin", branch=self.branch)
        self.staff = User.objects.create_user(username="stf", password="pass")
        UserProfile.objects.create(user=self.staff, role="staff", branch=self.branch)
        supplier = Supplier.objects.create(organization=self.org, name="Mart")
        self.gel = Item.objects.create(organization=self.org, name="Gel", unit="bottle")
        self.day = datetime.date.today() - datetime.timedelta(days=3)
        post_receipt(Receipt(branch=self.branch, supplier=supplier, bill_number="1", bill_date=self.day),
                     [{"item": self.gel, "quantity": D("10"), "rate": D("123"), "gst_rate": D("0")}])
        self.staff_url = reverse("inventory:staff_stock_count", args=[self.branch.id])
        self.today = datetime.date.today().isoformat()

    def staff_submit(self, qty="7"):
        self.client.login(username="stf", password="pass")
        return self.client.post(self.staff_url, {"as_at": self.today, f"count_{self.gel.id}": qty})

    def test_staff_sees_no_values_and_count_waits(self):
        self.client.login(username="stf", password="pass")
        page = self.client.get(self.staff_url)
        self.assertNotContains(page, "Avg cost")    # no cost shown to staff
        self.assertNotContains(page, "Book stock")  # no book stock shown to staff
        self.assertContains(page, "Quantity you counted")
        self.staff_submit()
        count = StockCount.objects.get()
        self.assertEqual((count.status, count.counted_by), ("pending", self.staff))
        self.assertEqual(StockBalance.objects.get().quantity, D("10"))  # stock not changed yet
        self.staff_submit("1")  # second submit while waiting is ignored
        self.assertEqual(count.lines.get().counted_qty, D("7"))

    def test_staff_cannot_review(self):
        self.staff_submit()
        count = StockCount.objects.get()
        response = self.client.get(reverse("inventory:stock_count_review", args=[self.branch.id, count.id]))
        self.assertEqual(response.status_code, 302)

    def test_admin_corrects_and_approves(self):
        self.staff_submit()
        count = StockCount.objects.get()
        self.client.login(username="adm", password="pass")
        url = reverse("inventory:stock_count_review", args=[self.branch.id, count.id])
        self.assertContains(self.client.get(url), "differs")
        self.client.post(url, {"action": "approve", f"count_{self.gel.id}": "6"})
        count.refresh_from_db()
        self.assertEqual((count.status, count.approved_by), ("approved", self.admin))
        line = count.lines.get()
        self.assertEqual((line.book_qty, line.counted_qty, line.used_qty), (D("10"), D("6"), D("4")))
        self.assertEqual(StockBalance.objects.get().quantity, D("6"))

    def test_send_back_and_resubmit(self):
        self.staff_submit()
        count = StockCount.objects.get()
        self.client.login(username="adm", password="pass")
        url = reverse("inventory:stock_count_review", args=[self.branch.id, count.id])
        self.client.post(url, {"action": "return", "return_note": ""})
        count.refresh_from_db()
        self.assertEqual(count.status, "pending")  # a reason is needed
        self.client.post(url, {"action": "return", "return_note": "Recount gel"})
        count.refresh_from_db()
        self.assertEqual(count.status, "returned")
        self.client.login(username="stf", password="pass")
        self.assertContains(self.client.get(self.staff_url), "Recount gel")
        self.staff_submit("8")
        count.refresh_from_db()
        self.assertEqual((count.status, count.lines.get().counted_qty), ("pending", D("8")))
        self.assertEqual(StockCount.objects.count(), 1)

    def test_admin_direct_entry_blocked_on_same_date(self):
        self.staff_submit()
        self.client.login(username="adm", password="pass")
        self.client.post(reverse("inventory:stock_count_new", args=[self.branch.id]),
                         {"as_at": self.today, f"count_{self.gel.id}": "5"})
        self.assertEqual(StockCount.objects.count(), 1)
