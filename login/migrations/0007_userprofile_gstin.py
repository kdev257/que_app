from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0006_guest_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='business_name',
            field=models.CharField(blank=True, help_text='Only if you want GST invoices in your business name', max_length=150),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='gstin',
            field=models.CharField(blank=True, help_text='Your business GSTIN (optional)', max_length=15, verbose_name='GSTIN'),
        ),
    ]
