import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('login', '0006_guest_created_at'),
        ('organization', '0007_branch_approval_and_rating'),
        ('queues', '0025_token_status_in_progress'),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('tags', models.CharField(blank=True, help_text='Comma separated tag keys', max_length=200)),
                ('comment', models.TextField(blank=True, max_length=1000)),
                ('display_name', models.CharField(help_text="Shown publicly, e.g. 'Rahul S.'", max_length=60)),
                ('is_hidden', models.BooleanField(default=False, help_text='Hidden by QuickQueue (abusive or fake)')),
                ('reply', models.TextField(blank=True, max_length=1000)),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='organization.branch')),
                ('guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviews', to='login.guest')),
                ('token', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review', to='queues.token')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
