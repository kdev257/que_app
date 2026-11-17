import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_itemcategory_account'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='stockcount',
            name='status',
            field=models.CharField(choices=[('pending', 'Waiting for approval'), ('returned', 'Sent back'), ('approved', 'Approved')], default='approved', max_length=10),
        ),
        migrations.AddField(
            model_name='stockcount',
            name='counted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_counts_counted', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='stockcount',
            name='approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_counts_approved', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='stockcount',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='stockcount',
            name='return_note',
            field=models.CharField(blank=True, help_text='Why it was sent back', max_length=255),
        ),
        migrations.AlterField(
            model_name='stockcountline',
            name='counted_qty',
            field=models.DecimalField(blank=True, decimal_places=3, help_text='Empty = not counted by staff (book stock is used)', max_digits=14, null=True),
        ),
    ]
