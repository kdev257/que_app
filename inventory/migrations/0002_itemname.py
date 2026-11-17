import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

UNITS = [('pcs', 'Pieces'), ('ml', 'ml'), ('l', 'Litre'), ('g', 'Gram'), ('kg', 'Kg'), ('box', 'Box'),
         ('pack', 'Pack'), ('bottle', 'Bottle'), ('tube', 'Tube'), ('set', 'Set')]


def link_existing(apps, schema_editor):
    """Put the names of items already added into the common list and link them."""
    Item = apps.get_model('inventory', 'Item')
    ItemName = apps.get_model('inventory', 'ItemName')
    for item in Item.objects.filter(master__isnull=True):
        master = ItemName.objects.filter(name__iexact=item.name).first()
        if master is None:
            master = ItemName.objects.create(name=item.name, unit=item.unit, category=item.category)
        Item.objects.filter(pk=item.pk).update(master=master)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemName',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('unit', models.CharField(choices=UNITS, default='pcs', help_text='Usual unit', max_length=10)),
                ('category', models.CharField(blank=True, max_length=60)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='item',
            name='master',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='inventory.itemname'),
        ),
        migrations.RunPython(link_existing, migrations.RunPython.noop),
    ]
