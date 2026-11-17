import datetime
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from login.models import User, UserProfile
from organization.models import Branch, Organization

from .models import Expense, ExpenseCategory, ExpenseMonthTotal


class ExpenseTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x", itc_allowed=False)
        owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=owner, role="org_admin", organization=self.org)
        self.client.login(username="own", password="pass")
        self.url = reverse("expenses:list", args=[self.branch.id])
        self.rent = ExpenseCategory.objects.get(name="Rent")  # example categories are ready

    def add(self, **extra):
        data = {"date": datetime.date.today().isoformat(), "category_choice": self.rent.id, "description": "Rent",
                "amount_entered": "11800", "amount_includes_gst": "on", "gst_rate": "18", "payment_mode": "bank"}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_add_stores_gst_and_month_total(self):
        self.add()
        e = Expense.objects.get()
        self.assertEqual((e.taxable_amount, e.gst_amount, e.total_amount), (D("10000.00"), D("1800.00"), D("11800.00")))
        self.assertFalse(e.itc_claimable)
        self.assertEqual(e.expense_value, D("11800.00"))  # GST is a cost when it cannot be claimed
        t = ExpenseMonthTotal.objects.get(branch=self.branch, month=e.month, category=self.rent)
        self.assertEqual((t.total_amount, t.expense_value, t.count), (D("11800.00"), D("11800.00"), 1))

    def test_itc_branch_with_gstin_keeps_gst_out(self):
        self.branch.itc_allowed, self.branch.is_gst_registered = True, True
        self.branch.save()
        self.add(paid_to_gstin="06ABCDE1234F1Z4")
        e = Expense.objects.get()
        self.assertTrue(e.itc_claimable)
        self.assertEqual(e.expense_value, D("10000.00"))

    def test_new_category_and_delete_updates_total(self):
        self.add(category_choice="__new__", new_category="Generator  diesel", gst_rate="0", amount_entered="500")
        cat = ExpenseCategory.objects.get(name="Generator diesel")
        e = Expense.objects.get(category=cat)
        self.client.post(reverse("expenses:delete", args=[self.branch.id, e.id]))
        self.assertFalse(Expense.objects.exists())
        t = ExpenseMonthTotal.objects.get(category=cat)
        self.assertEqual((t.total_amount, t.count), (D("0.00"), 0))

    def test_future_date_and_zero_amount_rejected(self):
        self.add(date=(datetime.date.today() + datetime.timedelta(days=1)).isoformat())
        self.add(amount_entered="0")
        self.assertFalse(Expense.objects.exists())

    def test_month_page_and_other_owner_blocked(self):
        self.add()
        page = self.client.get(self.url, {"month": datetime.date.today().strftime("%Y-%m")})
        self.assertContains(page, "11800")
        org2 = Organization.objects.create(name="Org2", email="z@t.com", phone="2")
        other = User.objects.create_user(username="x", password="pass")
        UserProfile.objects.create(user=other, role="org_admin", organization=org2)
        self.client.login(username="x", password="pass")
        self.assertEqual(self.client.get(self.url).status_code, 302)
