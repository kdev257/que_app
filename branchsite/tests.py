import datetime
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from login.models import User, UserProfile
from organization.models import Branch, Organization, Service, Service_Category, Service_Name

from .models import BranchSite, SiteOffer, SiteSection

TEMP_MEDIA = tempfile.mkdtemp()


def make_image(name="photo.jpg", size=(3000, 2000)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 80, 80)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BranchSiteTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cat = Service_Category.objects.create(name="Salon")
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.owner = User.objects.create_user(username="owner", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)
        self.branch = Branch.objects.create(name="Glow Salon", city="Pune", organization=self.org,
                                            services_category=cat, address="12 MG Road", pin_code="411001",
                                            phone="9876543210", is_approved=True)
        Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Hair Cut"), price=250)
        self.client.login(username="owner", password="pass")
        self.edit_url = reverse("branchsite:edit", args=[self.branch.id])

    def settings_data(self, **extra):
        data = {"form": "settings", "slug": "glow-salon-pune", "theme": "rose", "tagline": "Family salon",
                "about": "We care.", "hours_note": "Closed on Tuesdays",
                "show_offers": "on", "show_services": "on", "show_gallery": "on", "show_reviews": "on",
                "show_hours": "on", "show_location": "on", "show_contact": "on"}
        data.update(extra)
        return data

    def test_site_created_unpublished_and_only_owner_can_preview(self):
        self.assertEqual(self.client.get(self.edit_url).status_code, 200)
        site = BranchSite.objects.get(branch=self.branch)
        self.assertEqual(site.slug, "glow-salon-pune")
        self.assertFalse(site.is_published)
        page_url = reverse("branchsite:page", args=[site.slug])
        self.assertContains(self.client.get(page_url), "Preview")
        self.client.logout()
        self.assertEqual(self.client.get(page_url).status_code, 404)

    def test_publish_shows_page_to_everyone(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self.settings_data(is_published="on"))
        SiteOffer.objects.create(site=self.branch.site, title="20% off hair spa")
        SiteOffer.objects.create(site=self.branch.site, title="Old offer",
                                 valid_till=datetime.date.today() - datetime.timedelta(days=1))
        self.client.logout()
        response = self.client.get(reverse("branchsite:page", args=["glow-salon-pune"]))
        self.assertContains(response, "Glow Salon")
        self.assertContains(response, "Family salon")
        self.assertContains(response, "Hair Cut")
        self.assertContains(response, "20% off hair spa")
        self.assertNotContains(response, "Old offer")  # expired
        self.assertContains(response, "theme-rose")
        booking = reverse("branch_services", args=[self.branch.id]).replace("/", "%2F")
        self.assertContains(response, reverse("login_choice") + "?next=" + booking)  # Book -> login -> booking page
        self.client.login(username="owner", password="pass")
        response = self.client.get(reverse("branchsite:page", args=["glow-salon-pune"]))
        self.assertContains(response, reverse("branch_services", args=[self.branch.id]))  # logged in: Book -> booking

    def test_unapproved_branch_is_not_public(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self.settings_data(is_published="on"))
        self.branch.is_approved = False
        self.branch.save()
        self.client.logout()
        self.assertEqual(self.client.get(reverse("branchsite:page", args=["glow-salon-pune"])).status_code, 404)

    def test_hidden_section_not_shown(self):
        self.client.get(self.edit_url)
        data = self.settings_data(is_published="on")
        data.pop("show_services")
        self.client.post(self.edit_url, data)
        response = self.client.get(reverse("branchsite:page", args=["glow-salon-pune"]))
        self.assertNotContains(response, "Hair Cut")

    def test_slug_must_be_unique(self):
        other = Branch.objects.create(name="Other", organization=self.org, address="x")
        BranchSite.objects.create(branch=other, slug="taken")
        self.client.get(self.edit_url)
        response = self.client.post(self.edit_url, self.settings_data(slug="taken"))
        self.assertContains(response, "already taken")

    def test_photo_is_made_smaller(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, {"form": "photo", "image": make_image(), "caption": "Our chairs"})
        photo = self.branch.site.photos.get()
        with Image.open(photo.image.path) as img:
            self.assertLessEqual(max(img.size), 1600)
        self.client.post(reverse("branchsite:photo_delete", args=[self.branch.id, photo.id]))
        self.assertFalse(self.branch.site.photos.exists())

    def test_banner_upload(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self.settings_data(banner=make_image("banner.jpg", (4000, 1500))))
        site = BranchSite.objects.get(branch=self.branch)
        self.assertTrue(site.banner.name.startswith(f"sites/{self.branch.id}/banner/"))
        with Image.open(site.banner.path) as img:
            self.assertLessEqual(max(img.size), 1920)

    def test_other_owner_cannot_edit(self):
        org2 = Organization.objects.create(name="Org2", email="z@t.com", phone="3")
        intruder = User.objects.create_user(username="intruder", password="pass")
        UserProfile.objects.create(user=intruder, role="org_admin", organization=org2)
        self.client.login(username="intruder", password="pass")
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BranchSite.objects.filter(branch=self.branch).exists())

    def test_offer_add_and_hide(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, {"form": "offer", "title": "Free head massage", "details": "",
                                         "discount_type": "none", "discount_value": "0", "min_bill_amount": "0"})
        offer = SiteOffer.objects.get(title="Free head massage")
        self.client.post(reverse("branchsite:offer_action", args=[self.branch.id, offer.id]), {"action": "toggle"})
        offer.refresh_from_db()
        self.assertFalse(offer.is_active)


    def test_own_section_add_edit_hide(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self.settings_data(is_published="on"))
        self.client.post(self.edit_url, {"form": "section", "title": "Bridal packages", "body": "Full bridal makeup.",
                                         "sort_order": "1", "is_active": "on", "image": make_image()})
        sec = SiteSection.objects.get(title="Bridal packages")
        with Image.open(sec.image.path) as img:
            self.assertLessEqual(max(img.size), 1600)
        page_url = reverse("branchsite:page", args=["glow-salon-pune"])
        self.assertContains(self.client.get(page_url), "Full bridal makeup.")
        self.client.post(reverse("branchsite:section_edit", args=[self.branch.id, sec.id]),
                         {"title": "Bridal", "body": "New text", "sort_order": "2", "is_active": "on"})
        sec.refresh_from_db()
        self.assertEqual((sec.title, sec.body), ("Bridal", "New text"))
        self.client.post(reverse("branchsite:section_action", args=[self.branch.id, sec.id]), {"action": "toggle"})
        self.assertNotContains(self.client.get(page_url), "New text")
        self.client.post(reverse("branchsite:section_action", args=[self.branch.id, sec.id]), {"action": "delete"})
        self.assertFalse(SiteSection.objects.exists())


class PriceVisibilityTests(TestCase):
    """Prices show only after login or guest login."""

    def setUp(self):
        cat = Service_Category.objects.create(name="Salon")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Nails", organization=org, services_category=cat,
                                            address="x", is_approved=True)
        Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Gel Polish"), price=799)
        BranchSite.objects.create(branch=self.branch, slug="nails", is_published=True)

    def pages(self):
        return [reverse("branchsite:page", args=["nails"]), reverse("branch_services", args=[self.branch.id])]

    def test_visitor_sees_login_to_see_price(self):
        for url in self.pages():
            response = self.client.get(url)
            self.assertContains(response, "Gel Polish")
            self.assertContains(response, "Login to see price")
            self.assertNotContains(response, "799")

    def test_customer_and_guest_see_price(self):
        User.objects.create_user(username="cust", password="pass")
        self.client.login(username="cust", password="pass")
        for url in self.pages():
            self.assertContains(self.client.get(url), "799")
        self.client.logout()
        from login.models import Guest
        guest = Guest.objects.create(name="G", email="g@t.com", phone_no="1", pin_code="110001")
        session = self.client.session
        session["guest_id"] = guest.id
        session.save()
        self.assertContains(self.client.get(self.pages()[1]), "799")


class ListLinksToWebsiteTests(TestCase):
    def test_shop_list_opens_website_when_published(self):
        cat = Service_Category.objects.create(name="Nails")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        with_site = Branch.objects.create(name="Destello", organization=org, services_category=cat, address="x", is_approved=True)
        no_site = Branch.objects.create(name="Plain", organization=org, services_category=cat, address="y", is_approved=True)
        BranchSite.objects.create(branch=with_site, slug="destello", is_published=True)
        response = self.client.get(reverse("services_list", args=[cat.id]))
        self.assertContains(response, reverse("branchsite:page", args=["destello"]))
        self.assertContains(response, reverse("branch_services", args=[no_site.id]))
        self.assertNotContains(response, reverse("branch_services", args=[with_site.id]))


class BranchOfferDiscountTests(TestCase):
    """Owner's offers reduce the bill automatically; best offer wins; dates and limits respected."""

    def setUp(self):
        from decimal import Decimal
        self.D = Decimal
        cat = Service_Category.objects.create(name="Nails")
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", organization=org, services_category=cat,
                                            address="x", is_approved=True)
        self.site = BranchSite.objects.create(branch=self.branch, slug="destello")
        self.service = Service.objects.create(branch=self.branch, name=Service_Name.objects.create(name="Gel"),
                                              price=self.D("1000"))

    def offer(self, **kw):
        data = {"site": self.site, "title": "Offer", "discount_type": "percent", "discount_value": self.D("10")}
        data.update(kw)
        return SiteOffer.objects.create(**data)

    def test_percent_flat_min_and_cap(self):
        from .offers import offer_discount
        self.assertEqual(offer_discount(self.offer(), 1000), self.D("100.00"))
        self.assertEqual(offer_discount(self.offer(max_discount=self.D("50")), 1000), self.D("50.00"))
        self.assertEqual(offer_discount(self.offer(min_bill_amount=self.D("1500")), 1000), self.D("0.00"))
        self.assertEqual(offer_discount(self.offer(discount_type="flat", discount_value=self.D("150")), 1000), self.D("150.00"))
        self.assertEqual(offer_discount(self.offer(discount_type="none"), 1000), self.D("0.00"))

    def test_best_running_offer_wins(self):
        from .offers import best_offer
        today = datetime.date.today()
        self.offer(title="Inaugural 10%")
        self.offer(title="Old 50%", discount_value=self.D("50"), valid_till=today - datetime.timedelta(days=1))
        self.offer(title="Future 40%", discount_value=self.D("40"), start_date=today + datetime.timedelta(days=1))
        self.offer(title="Hidden 30%", discount_value=self.D("30"), is_active=False)
        offer, discount = best_offer(self.branch, self.D("1000"))
        self.assertEqual((offer.title, discount), ("Inaugural 10%", self.D("100.00")))

    def test_cart_shows_offer_and_token_invoice_use_it(self):
        from queues.models import Cart, CartItem, Token
        from billing.services import calculate_amounts
        self.offer(title="Inaugural 10%")
        user = User.objects.create_user(username="cust", password="pass")
        cart = Cart.objects.create(user=user, branch=self.branch)
        CartItem.objects.create(cart=cart, service=self.service)
        self.client.login(username="cust", password="pass")
        response = self.client.get(reverse("view_cart", args=[cart.id]))
        self.assertContains(response, "Inaugural 10%")
        self.assertEqual(response.context["discount_amount"], self.D("100.00"))
        # Invoice: GST on the amount after discount
        self.branch.is_gst_registered, self.branch.gst_percentage, self.branch.prices_include_gst = True, self.D("5"), False
        a = calculate_amounts(self.D("1000"), self.D("100"), self.D("0"), self.branch)
        self.assertEqual((a["taxable_amount"], a["gst_amount"]), (self.D("900.00"), self.D("45.00")))
