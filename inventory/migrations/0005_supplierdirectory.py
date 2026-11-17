import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

TYPES = [('beauty', 'Salon / beauty / wellness'), ('food', 'Restaurant / food'), ('general', 'All businesses')]
FIELDS = ["name", "phone", "whatsapp", "email", "gstin", "address", "city", "items_supplied"]
BEAUTY = ("salon", "saloon", "nail", "beauty", "parlour", "parlor", "spa", "barber", "hair", "makeup",
          "gym", "fitness", "yoga", "massage", "cosmetic")
FOOD = ("restaurant", "cafe", "dhaba", "food", "catering", "bakery", "kitchen", "hotel")


def branch_type(branch):
    sac = (branch.sac_code or "").strip()
    if sac.startswith("99972"):
        return "beauty"
    if sac == "996331":
        return "food"
    name = (branch.services_category.name if branch.services_category_id else "").lower()
    if any(w in name for w in FOOD):
        return "food"
    if any(w in name for w in BEAUTY):
        return "beauty"
    return "general"


def share_existing(apps, schema_editor):
    """Put suppliers already added into the shared list (business details only) and link them."""
    Supplier = apps.get_model('inventory', 'Supplier')
    SupplierDirectory = apps.get_model('inventory', 'SupplierDirectory')
    Branch = apps.get_model('organization', 'Branch')
    org_type = {}
    for b in Branch.objects.select_related('services_category').order_by('id'):
        org_type.setdefault(b.organization_id, branch_type(b))
    for s in Supplier.objects.filter(directory__isnull=True):
        entry = SupplierDirectory.objects.filter(name__iexact=s.name, city__iexact=s.city).first()
        if entry is None:
            entry = SupplierDirectory.objects.create(business_type=org_type.get(s.organization_id, "general"),
                                                     **{f: getattr(s, f) for f in FIELDS})
        Supplier.objects.filter(pk=s.pk).update(directory=entry)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_business_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupplierDirectory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('whatsapp', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('gstin', models.CharField(blank=True, max_length=15, verbose_name='GSTIN')),
                ('address', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(blank=True, max_length=80)),
                ('items_supplied', models.CharField(blank=True, max_length=255)),
                ('business_type', models.CharField(choices=TYPES, default='general', max_length=10)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'ordering': ['name'], 'verbose_name': 'Supplier directory entry', 'verbose_name_plural': 'Supplier directory'},
        ),
        migrations.AddField(
            model_name='supplier',
            name='directory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='copies', to='inventory.supplierdirectory'),
        ),
        migrations.RunPython(share_existing, migrations.RunPython.noop),
    ]
