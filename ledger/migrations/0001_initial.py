import django.db.models.deletion
from django.db import migrations, models

from ledger.chart import DEFAULT_ACCOUNTS, SYSTEM_MAPPINGS


def seed(apps, schema_editor):
    Account = apps.get_model('ledger', 'Account')
    AccountMapping = apps.get_model('ledger', 'AccountMapping')
    for code, name, kind, group in DEFAULT_ACCOUNTS:
        Account.objects.get_or_create(code=code, defaults={"name": name, "account_type": kind, "group": group})
    for key, _label, code in SYSTEM_MAPPINGS:
        AccountMapping.objects.get_or_create(key=key, defaults={"account": Account.objects.get(code=code)})


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='e.g. 6001', max_length=10, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('account_type', models.CharField(choices=[('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Capital / equity'), ('income', 'Income'), ('expense', 'Expense')], max_length=10)),
                ('group', models.CharField(blank=True, help_text='Tally-style group, e.g. Indirect Expenses', max_length=60)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['code']},
        ),
        migrations.CreateModel(
            name='AccountMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(choices=[(k, label) for k, label, _ in SYSTEM_MAPPINGS], max_length=40, unique=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mappings', to='ledger.account')),
            ],
            options={'ordering': ['key']},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
