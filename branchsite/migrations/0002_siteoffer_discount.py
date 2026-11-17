from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('branchsite', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteoffer',
            name='discount_type',
            field=models.CharField(choices=[('none', 'Display only (no discount on bill)'), ('percent', '% off the bill'), ('flat', 'Flat ₹ off the bill')], default='none', max_length=10),
        ),
        migrations.AddField(
            model_name='siteoffer',
            name='discount_value',
            field=models.DecimalField(decimal_places=2, default=0, help_text='e.g. 10 for 10% off, or 100 for ₹100 off', max_digits=10),
        ),
        migrations.AddField(
            model_name='siteoffer',
            name='min_bill_amount',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Offer applies only on bills of at least this amount (0 = any bill)', max_digits=10),
        ),
        migrations.AddField(
            model_name='siteoffer',
            name='max_discount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Biggest discount for % offers, e.g. 200 (empty = no limit)', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='siteoffer',
            name='start_date',
            field=models.DateField(blank=True, help_text='Leave empty to start today', null=True),
        ),
    ]
