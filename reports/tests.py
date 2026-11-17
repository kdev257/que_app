import datetime
from decimal import Decimal as D

from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice
from expenses.models import Expense, ExpenseCategory
from inventory.models import Item, Receipt, StockCount, StockMove, Supplier
from login.models import User, UserProfile
from organization.models import Branch, Organization

from .models import ProfitLossReport
from .services import generate_profit_loss

TODAY = datetime.date.today()
START = TODAY.replace(day=1)


class ProfitLossTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=self.org, address="x")
        self.branch2 = Branch.objects.create(name="Second", organization=self.org, address="y")
        self.owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)
        self.admin = User.objects.create_user(username="badmin", password="pass")
        UserProfile.objects.create(user=self.admin, role="branch_admin", organization=self.org, branch=self.branch)
        self.item = Item.objects.create(organization=self.org, name="Gel polish", unit="bottle")
        supplier = Supplier.objects.create(organization=self.org, name="Beauty Mart")
        # Opening stock 200 (before the period), purchase 1000 in the period, used 700 -> closing 500
        StockMove.objects.create(branch=self.branch, item=self.item, date=START - datetime.timedelta(days=1),
                                 kind="receipt", quantity=D("2"), value=D("200"))
        Receipt.objects.create(branch=self.branch, supplier=supplier, bill_number="B1", bill_date=START, stock_value=D("1000"))
        StockMove.objects.create(branch=self.branch, item=self.item, date=START, kind="receipt", quantity=D("10"), value=D("1000"))
        StockMove.objects.create(branch=self.branch, item=self.item, date=TODAY, kind="issue", quantity=D("-7"), value=D("-700"))
        Invoice.objects.create(branch=self.branch, seller_name="Destello", customer_name="A", taxable_amount=D("5000"))
        Invoice.objects.create(branch=self.branch2, seller_name="Second", customer_name="B", taxable_amount=D("3000"))
        rent = ExpenseCategory.objects.get_or_create(name="Rent")[0]
        Expense.objects.create(branch=self.branch, date=TODAY, category=rent, amount_entered=D("1500"),
                               expense_value=D("1500"), month=TODAY.strftime("%Y-%m"))

    def test_figures_are_stored(self):
        r = generate_profit_loss(self.org, [self.branch], START, TODAY, self.branch, self.owner)
        self.assertEqual((r.sales, r.net_sales), (D("5000"), D("5000")))
        self.assertEqual((r.opening_stock, r.purchases, r.closing_stock), (D("200"), D("1000"), D("500")))
        self.assertEqual(r.cost_of_items_used, D("700"))
        self.assertEqual(r.gross_profit, D("4300"))
        self.assertEqual(r.total_expenses, D("1500"))
        self.assertEqual(r.net_profit, D("2800"))
        self.assertEqual(r.lines.get().label, "Rent")
        self.assertTrue(r.warning_list)  # no closing stock count

    def test_no_warning_when_counted(self):
        StockCount.objects.create(branch=self.branch, as_at=TODAY, status="approved")
        r = generate_profit_loss(self.org, [self.branch], START, TODAY, self.branch)
        self.assertTrue(r.closing_stock_counted)
        self.assertFalse(r.warning_list)

    def test_generate_button_and_detail_page(self):
        self.client.login(username="badmin", password="pass")
        url = reverse("reports:profit_loss_generate", args=[self.branch.id])
        response = self.client.post(url, {"period_from": START.isoformat(), "period_to": TODAY.isoformat(), "scope": "all"})
        report = ProfitLossReport.objects.get()
        self.assertEqual(report.branch, self.branch)  # branch admin cannot pick "all branches"
        self.assertRedirects(response, reverse("reports:profit_loss_detail", args=[self.branch.id, report.id]))
        page = self.client.get(response.url)
        self.assertContains(page, "Net profit")
        self.assertContains(page, "2800.00")

    def test_owner_all_branches(self):
        self.client.login(username="own", password="pass")
        self.client.post(reverse("reports:profit_loss_generate", args=[self.branch.id]),
                         {"period_from": START.isoformat(), "period_to": TODAY.isoformat(), "scope": "all"})
        report = ProfitLossReport.objects.get()
        self.assertIsNone(report.branch)
        self.assertEqual(report.sales, D("8000"))
        self.assertContains(self.client.get(reverse("reports:profit_loss", args=[self.branch.id])), "All branches")

    def test_bad_dates(self):
        self.client.login(username="own", password="pass")
        url = reverse("reports:profit_loss_generate", args=[self.branch.id])
        self.client.post(url, {"period_from": TODAY.isoformat(), "period_to": START.isoformat() if START < TODAY else "2000-01-01"})
        self.client.post(url, {"period_from": START.isoformat(), "period_to": (TODAY + datetime.timedelta(days=1)).isoformat()})
        self.assertFalse(ProfitLossReport.objects.exists())

    def test_other_branch_admin_cannot_view(self):
        report = generate_profit_loss(self.org, [self.branch], START, TODAY, self.branch)
        other = User.objects.create_user(username="other", password="pass")
        UserProfile.objects.create(user=other, role="branch_admin", organization=self.org, branch=self.branch2)
        self.client.login(username="other", password="pass")
        response = self.client.get(reverse("reports:profit_loss_detail", args=[self.branch2.id, report.id]))
        self.assertEqual(response.status_code, 302)
