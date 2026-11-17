import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organization', '0015_service_category_sales_account'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfitLossReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period_from', models.DateField()),
                ('period_to', models.DateField()),
                ('sales', models.DecimalField(decimal_places=2, default=0, help_text='Taxable value of invoices (without GST)', max_digits=14)),
                ('credit_notes', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('net_sales', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('invoice_count', models.PositiveIntegerField(default=0)),
                ('opening_stock', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('purchases', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('closing_stock', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('cost_of_items_used', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('gross_profit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('total_expenses', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('net_profit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('closing_stock_counted', models.BooleanField(default=False, help_text='A closing stock count exists for the last day')),
                ('warnings', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(blank=True, help_text='Empty = all branches of the business', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pl_reports', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pl_reports', to='organization.organization')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ProfitLossLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=120)),
                ('account_code', models.CharField(blank=True, max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('sort', models.PositiveIntegerField(default=0)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='reports.profitlossreport')),
            ],
            options={'ordering': ['sort', 'label']},
        ),
    ]
