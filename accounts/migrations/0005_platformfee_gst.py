from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_platformfee'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformfee',
            name='gst_on_fee',
            field=models.BooleanField(default=False, help_text='Tick to charge GST on the booking fee'),
        ),
        migrations.AddField(
            model_name='platformfee',
            name='fee_gst_percentage',
            field=models.DecimalField(decimal_places=2, default=18.0, help_text='GST % on the booking fee', max_digits=5),
        ),
        migrations.AddField(
            model_name='platformfee',
            name='fee_includes_gst',
            field=models.BooleanField(default=True, help_text='Tick if the fee amount already includes GST'),
        ),
        migrations.AddField(
            model_name='platformfee',
            name='platform_gstin',
            field=models.CharField(blank=True, help_text='Platform GSTIN shown on invoices for the fee GST (optional)', max_length=15),
        ),
    ]
