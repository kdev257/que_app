from django.test import TestCase
from django.urls import reverse

from organization.models import Service_Category


class LandingPageTests(TestCase):
    def test_landing_shows_usp_and_service_links(self):
        cat = Service_Category.objects.create(name="Nails")
        response = self.client.get("/")
        self.assertContains(response, "Why QuickQueue")
        self.assertContains(response, reverse("services_list", args=[cat.id]))
        self.assertContains(response, reverse("index"))
        self.assertContains(response, reverse("workspace:signup"))
        self.assertContains(response, "mailto:adminquesaas@gmail.com")

    def test_services_page_moved_to_explore(self):
        self.assertEqual(reverse("index"), "/explore/")
        self.assertEqual(self.client.get("/explore/").status_code, 200)


class HelpPageTests(TestCase):
    def test_guides_open_and_are_linked_from_landing(self):
        landing = self.client.get("/")
        for slug in ("salon-setup", "restaurant-setup", "customers"):
            url = reverse("help_page", args=[slug])
            self.assertContains(landing, url)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse("help_page", args=["restaurant-setup"])), "Highway dhaba")
        self.assertEqual(self.client.get(reverse("help")).status_code, 200)
        self.assertEqual(self.client.get("/help/unknown/").status_code, 404)
