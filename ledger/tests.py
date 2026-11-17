from django.test import TestCase

from expenses.models import ExpenseCategory
from inventory.models import ItemCategory
from organization.models import Service_Category

from .models import Account, AccountMapping


class AccountCodeTests(TestCase):
    def test_chart_and_mappings_seeded(self):
        self.assertEqual(Account.objects.get(code="6001").name, "Rent")
        self.assertEqual(AccountMapping.account_for("output_cgst").code, "2100")
        self.assertEqual(AccountMapping.account_for("pay_upi").code, "1020")

    def test_categories_linked(self):
        self.assertEqual(ExpenseCategory.objects.get(name="Rent").account.code, "6001")
        self.assertEqual(ExpenseCategory.objects.create(name="Generator diesel").account.code, "6999")
        self.assertEqual(ItemCategory.objects.get(name="Nail products").account.code, "5001")
        self.assertEqual(ItemCategory.objects.create(name="Nail art").account.code, "5001")
        self.assertEqual(Service_Category.objects.create(name="Restaurant").sales_account.code, "4002")
        self.assertEqual(Service_Category.objects.create(name="Salon").sales_account.code, "4001")
