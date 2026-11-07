from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0005_branch_offers_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='is_gst_registered',
            field=models.BooleanField(default=False, help_text='Tick if this branch is registered under GST'),
        ),
        migrations.AddField(
            model_name='branch',
            name='gstin',
            field=models.CharField(blank=True, help_text='15-character GSTIN (required if GST registered)', max_length=15, null=True),
        ),
        migrations.AddField(
            model_name='branch',
            name='gst_percentage',
            field=models.DecimalField(decimal_places=2, default=18.0, help_text='Total GST % (split equally into CGST + SGST)', max_digits=5),
        ),
        migrations.AddField(
            model_name='branch',
            name='prices_include_gst',
            field=models.BooleanField(default=True, help_text='Tick if service/menu prices already include GST'),
        ),
    ]
