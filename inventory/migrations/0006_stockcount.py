import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def money(help_text=None):
    if help_text:
        return models.DecimalField(decimal_places=2, default=0, help_text=help_text, max_digits=14)
    return models.DecimalField(decimal_places=2, default=0, max_digits=14)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_supplierdirectory'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockCount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('as_at', models.DateField(default=datetime.date.today, verbose_name='Closing stock as at')),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('closing_value', money()),
                ('used_value', money('Cost of items used since the last count (negative = extra found)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_counts', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-as_at', '-id'], 'unique_together': {('branch', 'as_at')}},
        ),
        migrations.CreateModel(
            name='StockCountLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_qty', models.DecimalField(decimal_places=3, default=0, help_text='As per purchases and last count', max_digits=14)),
                ('counted_qty', models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ('used_qty', models.DecimalField(decimal_places=3, default=0, help_text='book - counted', max_digits=14)),
                ('avg_cost', models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ('closing_value', money()),
                ('used_value', money()),
                ('count', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='inventory.stockcount')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='count_lines', to='inventory.item')),
            ],
            options={'ordering': ['item__name']},
        ),
    ]
