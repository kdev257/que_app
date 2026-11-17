from django.db import migrations, models

TAX_TYPE_CHOICES = [('intra', 'CGST + SGST'), ('intra_ut', 'CGST + UTGST'), ('inter', 'IGST'), ('none', 'No GST')]


def money():
    return models.DecimalField(decimal_places=2, default=0, max_digits=12)


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_invoice_fee_gst'),
    ]

    operations = [
        migrations.AddField(model_name='invoice', name='supplier_state_code', field=models.CharField(blank=True, max_length=2)),
        migrations.AddField(model_name='invoice', name='place_of_supply_code', field=models.CharField(blank=True, max_length=2)),
        migrations.AddField(model_name='invoice', name='place_of_supply_name', field=models.CharField(blank=True, max_length=60)),
        migrations.AddField(model_name='invoice', name='tax_type', field=models.CharField(blank=True, choices=TAX_TYPE_CHOICES, max_length=10)),
        migrations.AddField(model_name='invoice', name='customer_gstin', field=models.CharField(blank=True, max_length=15)),
        migrations.AddField(model_name='invoice', name='customer_business_name', field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='invoice', name='utgst_amount', field=money()),
        migrations.AddField(model_name='invoice', name='igst_amount', field=money()),
        migrations.AddField(model_name='invoice', name='booking_fee_tax_type', field=models.CharField(blank=True, choices=TAX_TYPE_CHOICES, max_length=10)),
        migrations.AddField(model_name='invoice', name='booking_fee_cgst', field=money()),
        migrations.AddField(model_name='invoice', name='booking_fee_sgst', field=models.DecimalField(decimal_places=2, default=0, help_text='SGST or UTGST', max_digits=12)),
        migrations.AddField(model_name='invoice', name='booking_fee_igst', field=money()),
    ]
