from django.db import migrations, models

TYPES = [('beauty', 'Salon / beauty / wellness'), ('food', 'Restaurant / food'), ('general', 'All businesses')]
CATEGORY_TYPES = {
    "Nail products": "beauty", "Hair care": "beauty", "Skin care": "beauty", "Makeup": "beauty",
    "Spa & massage": "beauty", "Tools & equipment": "beauty", "Disposables (gloves, towels, foils)": "beauty",
    "Groceries": "food", "Vegetables & fruits": "food", "Dairy": "food", "Meat & seafood": "food",
    "Spices & masala": "food", "Oil & ghee": "food", "Beverages": "food", "Packaging": "food", "Gas & fuel": "food",
}
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


def fill(apps, schema_editor):
    ItemCategory = apps.get_model('inventory', 'ItemCategory')
    ItemName = apps.get_model('inventory', 'ItemName')
    Item = apps.get_model('inventory', 'Item')
    Branch = apps.get_model('organization', 'Branch')
    org_type = {}
    for b in Branch.objects.select_related('services_category').order_by('id'):
        org_type.setdefault(b.organization_id, branch_type(b))
    for cat in ItemCategory.objects.all():
        kind = CATEGORY_TYPES.get(cat.name)
        if kind is None:  # typed by a business: take that business's type
            item = Item.objects.filter(category__iexact=cat.name).first()
            kind = org_type.get(item.organization_id, "general") if item else "general"
        ItemCategory.objects.filter(pk=cat.pk).update(business_type=kind)
    for name in ItemName.objects.all():
        item = Item.objects.filter(master=name).first()
        kind = org_type.get(item.organization_id, "general") if item else "general"
        ItemName.objects.filter(pk=name.pk).update(business_type=kind)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_itemcategory'),
        ('organization', '0014_branch_sac_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcategory',
            name='business_type',
            field=models.CharField(choices=TYPES, default='general', max_length=10),
        ),
        migrations.AddField(
            model_name='itemname',
            name='business_type',
            field=models.CharField(choices=TYPES, default='general', max_length=10),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
