from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='booking_fee',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Booking fee (before its GST)', max_digits=12),
        ),
        migrations.AddField(
            model_name='invoice',
            name='booking_fee_gst_percentage',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='invoice',
            name='booking_fee_gst_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='invoice',
            name='platform_gstin',
            field=models.CharField(blank=True, max_length=15),
        ),
    ]
