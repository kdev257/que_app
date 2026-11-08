from django.db import migrations, models


def fill_icons(apps, schema_editor):
    from organization.service_styles import guess_style
    Service_Name = apps.get_model('organization', 'Service_Name')
    for sn in Service_Name.objects.filter(icon=''):
        sn.icon, sn.icon_group = guess_style(sn.name)
        sn.save(update_fields=['icon', 'icon_group'])


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0009_branch_social_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='service_name',
            name='icon',
            field=models.CharField(blank=True, help_text='Bootstrap icon class, e.g. bi-scissors', max_length=40),
        ),
        migrations.AddField(
            model_name='service_name',
            name='icon_group',
            field=models.CharField(choices=[('hair', 'Hair'), ('skin', 'Skin & face'), ('nails', 'Nails'), ('spa', 'Spa & massage'), ('grooming', 'Beard & grooming'), ('makeup', 'Make-up'), ('health', 'Health'), ('other', 'Other')], default='other', help_text='Colour group of the icon', max_length=20),
        ),
        migrations.RunPython(fill_icons, migrations.RunPython.noop),
    ]
