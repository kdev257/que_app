from django.db import migrations, models


def copy_category_sac(apps, schema_editor):
    Branch = apps.get_model('organization', 'Branch')
    for branch in Branch.objects.select_related('services_category').filter(sac_code=''):
        if branch.services_category_id and branch.services_category.sac_code:
            Branch.objects.filter(pk=branch.pk).update(sac_code=branch.services_category.sac_code)


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0013_branch_specified_premises_itc'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='sac_code',
            field=models.CharField(blank=True, max_length=8, verbose_name='Type of service (SAC code)'),
        ),
        migrations.RunPython(copy_category_sac, migrations.RunPython.noop),
    ]
