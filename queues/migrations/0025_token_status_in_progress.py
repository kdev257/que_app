from django.db import migrations, models


def serving_to_in_progress(apps, schema_editor):
    Token = apps.get_model('queues', 'Token')
    Token.objects.filter(status='serving').update(status='in_progress')


def in_progress_to_serving(apps, schema_editor):
    Token = apps.get_model('queues', 'Token')
    Token.objects.filter(status='in_progress').update(status='serving')


class Migration(migrations.Migration):

    dependencies = [
        ('queues', '0024_alter_token_payment_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='token',
            name='status',
            field=models.CharField(choices=[('waiting', 'Waiting'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('no_show', 'No Show')], default='waiting', max_length=20),
        ),
        migrations.RunPython(serving_to_in_progress, in_progress_to_serving),
    ]
