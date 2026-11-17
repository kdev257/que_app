import branchsite.models
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('branchsite', '0002_siteoffer_discount'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text="e.g. 'Our team' or 'Party orders'", max_length=80)),
                ('body', models.TextField(help_text='Text of the section', max_length=3000)),
                ('image', models.ImageField(blank=True, upload_to=branchsite.models._section_path)),
                ('sort_order', models.PositiveSmallIntegerField(default=1, help_text='Smaller number is shown first')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='branchsite.branchsite')),
            ],
            options={'ordering': ['sort_order', 'created_at']},
        ),
    ]
