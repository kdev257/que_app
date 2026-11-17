from django.db import migrations, models

STATE_CHOICES = [
    ('01', 'Jammu and Kashmir (01)'), ('02', 'Himachal Pradesh (02)'), ('03', 'Punjab (03)'), ('04', 'Chandigarh (04)'),
    ('05', 'Uttarakhand (05)'), ('06', 'Haryana (06)'), ('07', 'Delhi (07)'), ('08', 'Rajasthan (08)'),
    ('09', 'Uttar Pradesh (09)'), ('10', 'Bihar (10)'), ('11', 'Sikkim (11)'), ('12', 'Arunachal Pradesh (12)'),
    ('13', 'Nagaland (13)'), ('14', 'Manipur (14)'), ('15', 'Mizoram (15)'), ('16', 'Tripura (16)'),
    ('17', 'Meghalaya (17)'), ('18', 'Assam (18)'), ('19', 'West Bengal (19)'), ('20', 'Jharkhand (20)'),
    ('21', 'Odisha (21)'), ('22', 'Chhattisgarh (22)'), ('23', 'Madhya Pradesh (23)'), ('24', 'Gujarat (24)'),
    ('26', 'Dadra and Nagar Haveli and Daman and Diu (26)'), ('27', 'Maharashtra (27)'), ('29', 'Karnataka (29)'),
    ('30', 'Goa (30)'), ('31', 'Lakshadweep (31)'), ('32', 'Kerala (32)'), ('33', 'Tamil Nadu (33)'),
    ('34', 'Puducherry (34)'), ('35', 'Andaman and Nicobar Islands (35)'), ('36', 'Telangana (36)'),
    ('37', 'Andhra Pradesh (37)'), ('38', 'Ladakh (38)'), ('97', 'Other Territory (97)'),
]
RULE_CHOICES = [
    ('performed', 'Where service is performed (salon, restaurant, gym, spa, clinic) - always CGST+SGST'),
    ('general', "General rule (customer's state decides; may be IGST)"),
]


def fill_existing(apps, schema_editor):
    from organization.gst import PERFORMED_KEYWORDS, code_for_name
    Branch = apps.get_model('organization', 'Branch')
    Service_Category = apps.get_model('organization', 'Service_Category')
    for branch in Branch.objects.filter(gst_state_code=''):
        code = ''
        if branch.gstin and len(branch.gstin) == 15 and branch.gstin[:2].isdigit():
            code = branch.gstin[:2]  # GSTIN starts with the state code
        code = code or code_for_name(branch.state)
        if code:
            Branch.objects.filter(pk=branch.pk).update(gst_state_code=code)
    for cat in Service_Category.objects.all():
        if any(word in cat.name.lower() for word in PERFORMED_KEYWORDS):
            Service_Category.objects.filter(pk=cat.pk).update(place_of_supply_rule='performed')


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0010_service_name_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='gst_state_code',
            field=models.CharField(blank=True, choices=STATE_CHOICES, help_text='State where this branch is located (as per GST registration)', max_length=2, verbose_name='State'),
        ),
        migrations.AlterField(
            model_name='branch',
            name='gst_percentage',
            field=models.DecimalField(decimal_places=2, default=18.0, help_text='Total GST % (CGST + SGST together, or IGST)', max_digits=5),
        ),
        migrations.AddField(
            model_name='service_category',
            name='place_of_supply_rule',
            field=models.CharField(choices=RULE_CHOICES, default='general', max_length=20, verbose_name='GST place of supply rule'),
        ),
        migrations.RunPython(fill_existing, migrations.RunPython.noop),
    ]
