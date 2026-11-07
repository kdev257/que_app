import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('login', '0005_alter_guest_pin_code'),
        ('organization', '0006_branch_gst_fields'),
        ('queues', '0025_token_status_in_progress'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(blank=True, max_length=40, unique=True)),
                ('source', models.CharField(choices=[('service', 'Service'), ('restaurant', 'Restaurant')], default='service', max_length=20)),
                ('token_number', models.IntegerField(default=0)),
                ('service_date', models.DateField(blank=True, null=True)),
                ('seller_name', models.CharField(max_length=255)),
                ('seller_address', models.TextField(blank=True)),
                ('seller_phone', models.CharField(blank=True, max_length=20)),
                ('seller_email', models.EmailField(blank=True, max_length=254)),
                ('customer_name', models.CharField(max_length=255)),
                ('customer_email', models.EmailField(blank=True, max_length=254)),
                ('customer_phone', models.CharField(blank=True, max_length=20)),
                ('is_gst_invoice', models.BooleanField(default=False)),
                ('gstin', models.CharField(blank=True, max_length=15)),
                ('gst_percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('prices_include_gst', models.BooleanField(default=True)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, help_text='Sum of item amounts', max_digits=12)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('taxable_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('cgst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('sgst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('gst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('booking_fee', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('cashback_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('payment_status', models.CharField(blank=True, max_length=30)),
                ('payment_status_display', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('email_sent', models.BooleanField(default=False)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='invoices', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices_created', to=settings.AUTH_USER_MODEL)),
                ('customer_guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='login.guest')),
                ('customer_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to=settings.AUTH_USER_MODEL)),
                ('token', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoice', to='queues.token')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InvoiceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit_price', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='billing.invoice')),
            ],
        ),
    ]
