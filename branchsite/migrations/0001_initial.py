import branchsite.models
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organization', '0010_service_name_icon'),
    ]

    operations = [
        migrations.CreateModel(
            name='BranchSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Web address of the page: /b/<this-name>/. Only letters, numbers and dashes.', max_length=80, unique=True)),
                ('is_published', models.BooleanField(default=False, help_text='Tick to make the page visible to everyone.')),
                ('theme', models.CharField(choices=[('ocean', 'Ocean blue'), ('rose', 'Rose pink'), ('forest', 'Forest green'), ('sunset', 'Sunset orange'), ('night', 'Night (dark)')], default='ocean', max_length=20)),
                ('tagline', models.CharField(blank=True, help_text="One line under the name, e.g. 'Family salon since 2010'", max_length=120)),
                ('about', models.TextField(blank=True, help_text='A few lines about your business', max_length=2000)),
                ('hours_note', models.CharField(blank=True, help_text="e.g. 'Closed on Tuesdays'", max_length=120)),
                ('logo', models.ImageField(blank=True, upload_to=branchsite.models._logo_path)),
                ('banner', models.ImageField(blank=True, help_text='Wide photo shown at the top', upload_to=branchsite.models._banner_path)),
                ('show_offers', models.BooleanField(default=True, verbose_name='Show offers')),
                ('show_services', models.BooleanField(default=True, verbose_name='Show services / menu')),
                ('show_gallery', models.BooleanField(default=True, verbose_name='Show photo gallery')),
                ('show_reviews', models.BooleanField(default=True, verbose_name='Show reviews')),
                ('show_hours', models.BooleanField(default=True, verbose_name='Show opening hours')),
                ('show_location', models.BooleanField(default=True, verbose_name='Show address & map')),
                ('show_contact', models.BooleanField(default=True, verbose_name='Show contact & social links')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='site', to='organization.branch')),
            ],
            options={
                'verbose_name': 'Branch website',
            },
        ),
        migrations.CreateModel(
            name='SiteOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text="e.g. '20% off on hair spa'", max_length=80)),
                ('details', models.CharField(blank=True, help_text="e.g. 'Monday to Thursday, before 4 PM'", max_length=300)),
                ('valid_till', models.DateField(blank=True, help_text='Leave empty if there is no end date', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offers', to='branchsite.branchsite')),
            ],
            options={
                'ordering': ['-is_active', 'valid_till', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SitePhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to=branchsite.models._photo_path)),
                ('caption', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='branchsite.branchsite')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
