from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0008_service_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='website_url',
            field=models.URLField(blank=True, help_text='e.g. https://www.mysalon.in'),
        ),
        migrations.AddField(
            model_name='branch',
            name='instagram_url',
            field=models.URLField(blank=True, help_text='e.g. https://instagram.com/mysalon'),
        ),
        migrations.AddField(
            model_name='branch',
            name='facebook_url',
            field=models.URLField(blank=True, help_text='e.g. https://facebook.com/mysalon'),
        ),
        migrations.AddField(
            model_name='branch',
            name='google_maps_url',
            field=models.URLField(blank=True, help_text='Google Maps / Google reviews link of the branch'),
        ),
        migrations.AddField(
            model_name='branch',
            name='whatsapp_number',
            field=models.CharField(blank=True, help_text='Mobile number for WhatsApp chat, e.g. 9876543210', max_length=15),
        ),
    ]
