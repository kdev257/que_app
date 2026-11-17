"""
Branch mini website: each branch gets its own public page at /b/<slug>/.
The owner picks a colour theme, switches sections on/off and fills them in.
Everything shown on the page is stored here (no calculations on page load).
"""
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

THEMES = [
    ("ocean", "Ocean blue"),
    ("rose", "Rose pink"),
    ("forest", "Forest green"),
    ("sunset", "Sunset orange"),
    ("night", "Night (dark)"),
]

MAX_PHOTOS = 12
MAX_SECTIONS = 10


def _logo_path(instance, filename):
    return f"sites/{instance.branch_id}/logo/{filename}"


def _banner_path(instance, filename):
    return f"sites/{instance.branch_id}/banner/{filename}"


def _section_path(instance, filename):
    return f"sites/{instance.site.branch_id}/sections/{filename}"


def _photo_path(instance, filename):
    return f"sites/{instance.site.branch_id}/gallery/{filename}"


class BranchSite(models.Model):
    branch = models.OneToOneField("organization.Branch", on_delete=models.CASCADE, related_name="site")
    slug = models.SlugField(max_length=80, unique=True,
                            help_text="Web address of the page: /b/<this-name>/. Only letters, numbers and dashes.")
    is_published = models.BooleanField(default=False, help_text="Tick to make the page visible to everyone.")
    theme = models.CharField(max_length=20, choices=THEMES, default="ocean")

    # Content
    tagline = models.CharField(max_length=120, blank=True, help_text="One line under the name, e.g. 'Family salon since 2010'")
    about = models.TextField(max_length=2000, blank=True, help_text="A few lines about your business")
    hours_note = models.CharField(max_length=120, blank=True, help_text="e.g. 'Closed on Tuesdays'")
    logo = models.ImageField(upload_to=_logo_path, blank=True)
    banner = models.ImageField(upload_to=_banner_path, blank=True, help_text="Wide photo shown at the top")

    # Sections (on / off)
    show_offers = models.BooleanField(default=True, verbose_name="Show offers")
    show_services = models.BooleanField(default=True, verbose_name="Show services / menu")
    show_gallery = models.BooleanField(default=True, verbose_name="Show photo gallery")
    show_reviews = models.BooleanField(default=True, verbose_name="Show reviews")
    show_hours = models.BooleanField(default=True, verbose_name="Show opening hours")
    show_location = models.BooleanField(default=True, verbose_name="Show address & map")
    show_contact = models.BooleanField(default=True, verbose_name="Show contact & social links")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Branch website"

    def __str__(self):
        return f"Website of {self.branch.name}"

    @staticmethod
    def unique_slug(branch, exclude_id=None):
        base = slugify(f"{branch.name} {branch.city or ''}")[:70] or f"branch-{branch.id}"
        slug, n = base, 2
        qs = BranchSite.objects.all()
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    @classmethod
    def for_branch(cls, branch):
        """Return the branch's site, creating an unpublished one on first use."""
        site = cls.objects.filter(branch=branch).first()
        if site is None:
            site = cls.objects.create(branch=branch, slug=cls.unique_slug(branch))
        return site


class SiteOffer(models.Model):
    DISCOUNT_TYPES = [
        ("none", "Display only (no discount on bill)"),
        ("percent", "% off the bill"),
        ("flat", "Flat ₹ off the bill"),
    ]
    site = models.ForeignKey(BranchSite, on_delete=models.CASCADE, related_name="offers")
    title = models.CharField(max_length=80, help_text="e.g. '20% off on hair spa'")
    details = models.CharField(max_length=300, blank=True, help_text="e.g. 'Monday to Thursday, before 4 PM'")
    # Discount applied automatically on the bill (best running offer wins; offers do not add up)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default="none")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         help_text="e.g. 10 for 10% off, or 100 for ₹100 off")
    min_bill_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          help_text="Offer applies only on bills of at least this amount (0 = any bill)")
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Biggest discount for % offers, e.g. 200 (empty = no limit)")
    start_date = models.DateField(null=True, blank=True, help_text="Leave empty to start today")
    valid_till = models.DateField(null=True, blank=True, help_text="Leave empty if there is no end date")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_active", "valid_till", "-created_at"]

    def __str__(self):
        return self.title


class SitePhoto(models.Model):
    site = models.ForeignKey(BranchSite, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=_photo_path)
    caption = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.caption or f"Photo {self.id}"


class SiteSection(models.Model):
    """Extra section the owner adds to the website (e.g. 'Our team', 'Party orders')."""
    site = models.ForeignKey(BranchSite, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=80, help_text="e.g. 'Our team' or 'Party orders'")
    body = models.TextField(max_length=3000, help_text="Text of the section")
    image = models.ImageField(upload_to=_section_path, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=1, help_text="Smaller number is shown first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return self.title
