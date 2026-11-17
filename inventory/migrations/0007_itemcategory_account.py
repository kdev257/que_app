import django.db.models.deletion
from django.db import migrations, models


def link(apps, schema_editor):
    Account = apps.get_model('ledger', 'Account')
    ItemCategory = apps.get_model('inventory', 'ItemCategory')
    ItemCategory.objects.filter(account__isnull=True).update(account=Account.objects.filter(code="5001").first())


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_stockcount'),
        ('ledger', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcategory',
            name='account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='item_categories', to='ledger.account', verbose_name='Purchase account code'),
        ),
        migrations.RunPython(link, migrations.RunPython.noop),
    ]
