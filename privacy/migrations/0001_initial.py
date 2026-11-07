import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('login', '0006_guest_created_at'),
        ('organization', '0006_branch_gst_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrivacyNotice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=20, unique=True)),
                ('title', models.CharField(default='Privacy Notice', max_length=200)),
                ('body', models.TextField(help_text="Plain text. Blank lines start a new paragraph. Lines starting with '- ' become bullet points.")),
                ('effective_from', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_current', models.BooleanField(default=False, help_text='Only one notice should be current.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-effective_from']},
        ),
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('service', 'Bookings, queue updates, payments and invoices')], default='service', max_length=30)),
                ('age_confirmed', models.BooleanField(default=False, help_text='User confirmed they are 18 or older')),
                ('given_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('withdrawn_at', models.DateTimeField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='consents', to='login.guest')),
                ('notice', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='consents', to='privacy.privacynotice')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='consents', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-given_at']},
        ),
        migrations.CreateModel(
            name='DataRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, max_length=30, unique=True)),
                ('contact_name', models.CharField(blank=True, max_length=150)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('request_type', models.CharField(choices=[('access', 'Get a summary of my data'), ('correction', 'Correct / update my data'), ('erasure', 'Delete my data'), ('withdraw_consent', 'Withdraw consent'), ('nominate', 'Nominate a person (in case of death or incapacity)'), ('grievance', 'Complaint / grievance')], max_length=30)),
                ('details', models.TextField(blank=True)),
                ('nominee_name', models.CharField(blank=True, max_length=150)),
                ('nominee_contact', models.CharField(blank=True, max_length=150)),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In progress'), ('resolved', 'Resolved'), ('rejected', 'Rejected')], default='open', max_length=20)),
                ('response', models.TextField(blank=True, help_text='Reply to the user (emailed when resolved/rejected)')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('erase_after', models.DateField(blank=True, null=True)),
                ('guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_requests', to='login.guest')),
                ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handled_data_requests', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ProcessingLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('action', models.CharField(choices=[('register', 'Account created'), ('guest_login', 'Guest details collected'), ('login', 'Login'), ('consent_given', 'Consent given'), ('consent_withdrawn', 'Consent withdrawn'), ('booking', 'Booking / order created'), ('invoice_created', 'Invoice created'), ('invoice_viewed', 'Invoice viewed'), ('profile_updated', 'Profile updated'), ('data_exported', 'Data downloaded by user'), ('request_created', 'Rights request / grievance created'), ('erasure_scheduled', 'Erasure scheduled'), ('erasure_notice', 'Pre-erasure notice sent'), ('anonymised', 'Personal data anonymised'), ('breach_notice', 'Breach notice sent')], max_length=30)),
                ('object_type', models.CharField(blank=True, max_length=50)),
                ('object_id', models.CharField(blank=True, max_length=50)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('subject_guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='login.guest')),
                ('subject_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ErasureNotice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notified_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('erase_on_or_after', models.DateTimeField()),
                ('cancelled', models.BooleanField(default=False, help_text='Set if the user became active again')),
                ('guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='login.guest')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='BreachIncident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('detected_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('nature_and_extent', models.TextField(help_text='What happened and what data was affected')),
                ('likely_impact', models.TextField(blank=True, help_text='Likely consequences for users')),
                ('mitigation', models.TextField(blank=True, help_text='Steps taken / being taken')),
                ('user_safety_steps', models.TextField(blank=True, help_text='What users should do to protect themselves')),
                ('all_users_affected', models.BooleanField(default=False)),
                ('board_report_due', models.DateTimeField(blank=True, help_text='Detailed report to the Data Protection Board due by', null=True)),
                ('reported_to_board_at', models.DateTimeField(blank=True, null=True)),
                ('board_reference', models.CharField(blank=True, max_length=100)),
                ('users_notified_at', models.DateTimeField(blank=True, null=True)),
                ('users_notified_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('open', 'Open'), ('contained', 'Contained'), ('closed', 'Closed')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('affected_branches', models.ManyToManyField(blank=True, help_text='Users who booked at these branches will be notified', to='organization.branch')),
            ],
            options={'ordering': ['-detected_at']},
        ),
    ]
