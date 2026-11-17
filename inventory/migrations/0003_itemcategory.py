import django.utils.timezone
from django.db import migrations, models

DEFAULT_CATEGORIES = [
    "Nail products", "Hair care", "Skin care", "Makeup", "Spa & massage", "Tools & equipment",
    "Disposables (gloves, towels, foils)", "Cleaning & hygiene", "Groceries", "Vegetables & fruits",
    "Dairy", "Meat & seafood", "Spices & masala", "Oil & ghee", "Beverages", "Packaging",
    "Gas & fuel", "Stationery", "Other",
]


def seed(apps, schema_editor):
    ItemCategory = apps.get_model('inventory', 'ItemCategory')
    Item = apps.get_model('inventory', 'Item')
    names = set(DEFAULT_CATEGORIES)
    names.update(c for c in Item.objects.exclude(category='').values_list('category', flat=True))  # keep ones already typed
    for name in sorted(names):
        if not ItemCategory.objects.filter(name__iexact=name).exists():
            ItemCategory.objects.create(name=name[:60])


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_itemname'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'ordering': ['name'], 'verbose_name_plural': 'Item categories'},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
