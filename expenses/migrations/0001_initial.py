import datetime

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

DEFAULT_EXPENSE_CATEGORIES = [
    "Rent", "Salaries & wages", "Electricity", "Water", "Internet & phone", "Repairs & maintenance",
    "Marketing & ads", "Bank & payment charges", "Professional fees (CA, legal)", "Licences & fees",
    "Travel & conveyance", "Staff food & welfare", "Laundry", "Commission paid", "Software & subscriptions",
    "Insurance", "Other",
]


def seed(apps, schema_editor):
    ExpenseCategory = apps.get_model('expenses', 'ExpenseCategory')
    for name in DEFAULT_EXPENSE_CATEGORIES:
        ExpenseCategory.objects.get_or_create(name=name)


def money(help_text=None, digits=12):
    if help_text:
        return models.DecimalField(decimal_places=2, default=0, help_text=help_text, max_digits=digits)
    return models.DecimalField(decimal_places=2, default=0, max_digits=digits)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organization', '0014_branch_sac_code'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'ordering': ['name'], 'verbose_name_plural': 'Expense categories'},
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=datetime.date.today)),
                ('description', models.CharField(blank=True, help_text='e.g. November rent', max_length=200)),
                ('paid_to', models.CharField(blank=True, help_text='e.g. landlord, electricity board', max_length=150)),
                ('paid_to_gstin', models.CharField(blank=True, max_length=15, verbose_name='Paid to GSTIN')),
                ('amount_entered', models.DecimalField(decimal_places=2, help_text='Amount as on the bill', max_digits=12)),
                ('amount_includes_gst', models.BooleanField(default=True)),
                ('gst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('payment_mode', models.CharField(choices=[('cash', 'Cash'), ('upi', 'UPI'), ('card', 'Card'), ('bank', 'Bank transfer'), ('other', 'Other')], default='cash', max_length=10)),
                ('bill_file', models.FileField(blank=True, upload_to='expense_bills/')),
                ('taxable_amount', money()),
                ('gst_amount', money()),
                ('total_amount', money()),
                ('itc_claimable', models.BooleanField(default=False)),
                ('expense_value', money('Cost for profit & loss (GST included when it cannot be claimed)')),
                ('month', models.CharField(db_index=True, help_text='YYYY-MM', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenses', to='organization.branch')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expenses', to='expenses.expensecategory')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-date', '-id']},
        ),
        migrations.CreateModel(
            name='ExpenseMonthTotal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(help_text='YYYY-MM', max_length=7)),
                ('total_amount', money(digits=14)),
                ('gst_claimable', money(digits=14)),
                ('expense_value', money(digits=14)),
                ('count', models.PositiveIntegerField(default=0)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expense_totals', to='organization.branch')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='month_totals', to='expenses.expensecategory')),
            ],
            options={'ordering': ['month', 'category__name'], 'unique_together': {('branch', 'month', 'category')}},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
