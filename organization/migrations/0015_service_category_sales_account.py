import django.db.models.deletion
from django.db import migrations, models

FOOD = ("restaurant", "cafe", "dhaba", "food", "catering", "bakery")


def link(apps, schema_editor):
    Account = apps.get_model('ledger', 'Account')
    Service_Category = apps.get_model('organization', 'Service_Category')
    services, food = Account.objects.filter(code="4001").first(), Account.objects.filter(code="4002").first()
    for cat in Service_Category.objects.filter(sales_account__isnull=True):
        is_food = any(w in cat.name.lower() for w in FOOD)
        Service_Category.objects.filter(pk=cat.pk).update(sales_account=food if is_food else services)


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0014_branch_sac_code'),
        ('ledger', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='service_category',
            name='sales_account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_categories', to='ledger.account', verbose_name='Sales account code'),
        ),
        migrations.RunPython(link, migrations.RunPython.noop),
    ]
