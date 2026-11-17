from django.db import migrations, models


def fill_itc(apps, schema_editor):
    Branch = apps.get_model('organization', 'Branch')
    for branch in Branch.objects.select_related('services_category'):
        itc = branch.services_category.itc_allowed if branch.services_category_id else True
        Branch.objects.filter(pk=branch.pk).update(itc_allowed=itc)


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0012_sac_rate_invoice_prefix'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='specified_premises',
            field=models.BooleanField(default=False, help_text='Tick only if this restaurant is in a hotel where any room was above Rs 7,500 per day last year, or the hotel opted for 18% with ITC', verbose_name='Restaurant in a hotel (specified premises)'),
        ),
        migrations.AddField(
            model_name='branch',
            name='itc_allowed',
            field=models.BooleanField(default=True, verbose_name='Input tax credit allowed'),
        ),
        migrations.RunPython(fill_itc, migrations.RunPython.noop),
    ]
