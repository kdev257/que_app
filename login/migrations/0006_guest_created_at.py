import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0005_alter_guest_pin_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='guest',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
