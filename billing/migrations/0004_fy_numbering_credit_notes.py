import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def money():
    return models.DecimalField(decimal_places=2, default=0, max_digits=12)


def rate(help_text=None):
    if help_text:
        return models.DecimalField(decimal_places=2, default=0, help_text=help_text, max_digits=5)
    return models.DecimalField(decimal_places=2, default=0, max_digits=5)


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_invoice_place_of_supply'),
        ('organization', '0012_sac_rate_invoice_prefix'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='invoice_number',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(model_name='invoice', name='financial_year', field=models.CharField(blank=True, help_text='e.g. 26-27', max_length=5)),
        migrations.AddField(model_name='invoice', name='serial_number', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='invoice', name='cgst_rate', field=rate()),
        migrations.AddField(model_name='invoice', name='sgst_rate', field=rate('SGST or UTGST rate')),
        migrations.AddField(model_name='invoice', name='igst_rate', field=rate()),
        migrations.AddField(model_name='invoice', name='payment_mode', field=models.CharField(blank=True, choices=[('cash', 'Cash'), ('upi', 'UPI'), ('card', 'Card'), ('online', 'Online (QuickQueue)'), ('other', 'Other')], max_length=10)),
        migrations.AddField(model_name='invoice', name='credited_amount', field=money()),
        migrations.AddField(model_name='invoiceitem', name='sac_code', field=models.CharField(blank=True, max_length=8)),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.UniqueConstraint(fields=('branch', 'invoice_number'), name='unique_invoice_number_per_branch'),
        ),
        migrations.CreateModel(
            name='DocumentSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_type', models.CharField(choices=[('invoice', 'Invoice'), ('credit_note', 'Credit note')], max_length=20)),
                ('financial_year', models.CharField(max_length=5)),
                ('last_number', models.PositiveIntegerField(default=0)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_sequences', to='organization.branch')),
            ],
            options={
                'unique_together': {('branch', 'doc_type', 'financial_year')},
            },
        ),
        migrations.CreateModel(
            name='CreditNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=40)),
                ('financial_year', models.CharField(max_length=5)),
                ('serial_number', models.PositiveIntegerField(default=0)),
                ('reason', models.CharField(choices=[('cancelled', 'Bill cancelled'), ('refund', 'Refund to customer'), ('discount', 'Discount after billing'), ('error', 'Correction of mistake'), ('other', 'Other')], max_length=20)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('tax_type', models.CharField(blank=True, max_length=10)),
                ('taxable_amount', money()),
                ('cgst_amount', money()),
                ('sgst_amount', money()),
                ('utgst_amount', money()),
                ('igst_amount', money()),
                ('gst_amount', money()),
                ('total_amount', money()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='credit_notes', to='organization.branch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credit_notes_created', to=settings.AUTH_USER_MODEL)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='credit_notes', to='billing.invoice')),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('branch', 'number'), name='unique_credit_note_number_per_branch')],
            },
        ),
    ]
