import datetime

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

UNITS = [('pcs', 'Pieces'), ('ml', 'ml'), ('l', 'Litre'), ('g', 'Gram'), ('kg', 'Kg'), ('box', 'Box'),
         ('pack', 'Pack'), ('bottle', 'Bottle'), ('tube', 'Tube'), ('set', 'Set')]


def money(help_text=None, digits=14):
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
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('contact_person', models.CharField(blank=True, max_length=100)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('whatsapp', models.CharField(blank=True, help_text='Mobile number for WhatsApp, e.g. 9876543210', max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('gstin', models.CharField(blank=True, max_length=15, verbose_name='GSTIN')),
                ('address', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(blank=True, max_length=80)),
                ('items_supplied', models.CharField(blank=True, help_text='e.g. Gel polish, nail files, acetone', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suppliers', to='organization.organization')),
            ],
            options={'ordering': ['name'], 'unique_together': {('organization', 'name')}},
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='e.g. Gel polish - Red 15 ml', max_length=150)),
                ('unit', models.CharField(choices=UNITS, default='pcs', max_length=10)),
                ('category', models.CharField(blank=True, help_text='e.g. Nail products, Cleaning, Groceries', max_length=60)),
                ('hsn_code', models.CharField(blank=True, max_length=8, verbose_name='HSN code')),
                ('min_stock', models.DecimalField(decimal_places=3, default=0, help_text='Alert when stock falls below this quantity', max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_items', to='organization.organization')),
            ],
            options={'ordering': ['name'], 'unique_together': {('organization', 'name')}},
        ),
        migrations.CreateModel(
            name='StockBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ('value', money()),
                ('avg_cost', models.DecimalField(decimal_places=4, default=0, help_text='Weighted average cost per unit', max_digits=14)),
                ('is_low', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_balances', to='organization.branch')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balances', to='inventory.item')),
            ],
            options={'ordering': ['item__name'], 'unique_together': {('branch', 'item')}},
        ),
        migrations.CreateModel(
            name='Receipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bill_number', models.CharField(help_text="Supplier's bill / invoice number", max_length=40)),
                ('bill_date', models.DateField(default=datetime.date.today)),
                ('rates_include_gst', models.BooleanField(default=False)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('bill_file', models.FileField(blank=True, help_text='Photo or PDF of the bill (optional)', upload_to='purchase_bills/')),
                ('taxable_amount', money()),
                ('gst_amount', money()),
                ('total_amount', money()),
                ('stock_value', money('Amount added to stock')),
                ('itc_claimable', models.BooleanField(default=False, help_text='Branch can claim input tax credit on this bill')),
                ('supplier_gstin', models.CharField(blank=True, max_length=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipts', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipts', to='inventory.supplier')),
            ],
            options={'ordering': ['-bill_date', '-id']},
        ),
        migrations.CreateModel(
            name='ReceiptLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=12)),
                ('rate', models.DecimalField(decimal_places=2, help_text='Rate per unit as on the bill', max_digits=12)),
                ('gst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('taxable_amount', money()),
                ('gst_amount', money()),
                ('total_amount', money()),
                ('stock_value', money()),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipt_lines', to='inventory.item')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='inventory.receipt')),
            ],
        ),
        migrations.CreateModel(
            name='StockMove',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=datetime.date.today)),
                ('kind', models.CharField(choices=[('receipt', 'Receipt'), ('issue', 'Issue (used)'), ('adjust', 'Adjustment')], max_length=10)),
                ('quantity', models.DecimalField(decimal_places=3, help_text='+ in, - out', max_digits=14)),
                ('value', models.DecimalField(decimal_places=2, help_text='+ in, - out (at cost)', max_digits=14)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_moves', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='moves', to='inventory.item')),
                ('receipt_line', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='moves', to='inventory.receiptline')),
            ],
            options={'ordering': ['-date', '-id']},
        ),
    ]
