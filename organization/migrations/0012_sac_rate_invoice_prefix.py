from decimal import Decimal

from django.db import migrations, models


def fill_defaults(apps, schema_editor):
    from organization.gst import category_defaults
    Service_Category = apps.get_model('organization', 'Service_Category')
    Branch = apps.get_model('organization', 'Branch')
    for cat in Service_Category.objects.all():
        found = category_defaults(cat.name)
        if found:
            sac, rate, itc = found
            Service_Category.objects.filter(pk=cat.pk).update(sac_code=sac, default_gst_rate=Decimal(rate), itc_allowed=itc)
    # Invoice prefix for every branch: initials of the name, unique within the organization
    taken = {}
    for branch in Branch.objects.order_by('id'):
        words = ["".join(ch for ch in w if ch.isalnum()) for w in (branch.name or "").upper().split()]
        words = [w for w in words if w]
        base = ("".join(w[0] for w in words)[:3] if len(words) > 1 else (words[0][:3] if words else "")) or "INV"
        used = taken.setdefault(branch.organization_id, set())
        prefix, n = base, 2
        while prefix in used:
            prefix = f"{base}{n}"
            n += 1
        used.add(prefix)
        Branch.objects.filter(pk=branch.pk).update(invoice_prefix=prefix[:4])


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0011_gst_state_and_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='invoice_prefix',
            field=models.CharField(blank=True, help_text='1-4 letters/digits, e.g. DST. Invoice numbers look like DST/26-27/00001.', max_length=4),
        ),
        migrations.AddField(
            model_name='service_category',
            name='sac_code',
            field=models.CharField(blank=True, help_text='Printed on invoices, e.g. 999721 hair, 999722 nails/beauty, 996331 restaurant', max_length=8, verbose_name='SAC code'),
        ),
        migrations.AddField(
            model_name='service_category',
            name='default_gst_rate',
            field=models.DecimalField(decimal_places=2, default=18, help_text='Salon/beauty/spa/gym/restaurant: 5% (since 22-09-2025)', max_digits=5, verbose_name='Usual GST %'),
        ),
        migrations.AddField(
            model_name='service_category',
            name='itc_allowed',
            field=models.BooleanField(default=True, help_text='Untick for 5% services where GST paid on purchases cannot be claimed', verbose_name='Input tax credit allowed'),
        ),
        migrations.AddField(
            model_name='service',
            name='sac_code',
            field=models.CharField(blank=True, help_text='Leave empty to use the SAC code of the business type', max_length=8, verbose_name='SAC code'),
        ),
        migrations.RunPython(fill_defaults, migrations.RunPython.noop),
    ]
