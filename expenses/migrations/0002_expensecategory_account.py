import django.db.models.deletion
from django.db import migrations, models


def link(apps, schema_editor):
    from ledger.chart import EXPENSE_CATEGORY_CODES
    Account = apps.get_model('ledger', 'Account')
    ExpenseCategory = apps.get_model('expenses', 'ExpenseCategory')
    for cat in ExpenseCategory.objects.filter(account__isnull=True):
        code = EXPENSE_CATEGORY_CODES.get(cat.name, "6999")
        ExpenseCategory.objects.filter(pk=cat.pk).update(account=Account.objects.filter(code=code).first())


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
        ('ledger', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expensecategory',
            name='account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expense_categories', to='ledger.account', verbose_name='Account code'),
        ),
        migrations.RunPython(link, migrations.RunPython.noop),
    ]
