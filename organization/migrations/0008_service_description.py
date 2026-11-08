from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0007_branch_approval_and_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='description',
            field=models.TextField(blank=True, help_text="Short description shown to customers, e.g. 'Includes wash and blow-dry'", max_length=500),
        ),
    ]
