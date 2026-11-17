from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_platformfee_gst'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformfee',
            name='platform_state_code',
            field=models.CharField(blank=True, help_text='GST state code where QuickQueue is registered, e.g. 27. Decides CGST+SGST or IGST on the fee. Leave empty to use the first 2 digits of the platform GSTIN.', max_length=2),
        ),
    ]
