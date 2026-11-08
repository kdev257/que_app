from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0006_branch_gst_fields'),
    ]

    operations = [
        # Existing branches are already live, so they start as approved
        migrations.AddField(
            model_name='branch',
            name='is_approved',
            field=models.BooleanField(default=True, help_text='Approved by QuickQueue. Only approved branches are shown to customers.'),
        ),
        migrations.AddField(
            model_name='branch',
            name='rating_avg',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=3),
        ),
        migrations.AddField(
            model_name='branch',
            name='rating_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
