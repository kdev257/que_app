from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from login.models import StaffRequest, User, UserProfile
from organization.models import Branch, Organization, Service_Category
from restaurants.models import Highway, HighwayBranch, HighwaySegment


class StaffJoinTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.branch = Branch.objects.create(name="Destello", city="Gurgaon", organization=self.org, is_approved=True,
                                            services_category=Service_Category.objects.create(name="Nails"))
        self.other = Branch.objects.create(name="Other", organization=self.org, is_approved=True)
        self.owner = User.objects.create_user(username="own", password="pass")
        UserProfile.objects.create(user=self.owner, role="org_admin", organization=self.org)

    def register(self, **extra):
        data = {"username": "ravi", "first_name": "Ravi", "last_name": "K", "email": "r@t.com",
                "password1": "S3cure-pass-123", "password2": "S3cure-pass-123",
                "age_confirm": "on", "accept_notice": "on", "account_type": "staff", "staff_branch": self.branch.id}
        data.update(extra)
        return self.client.post(reverse("register"), data)

    def test_staff_must_pick_branch(self):
        self.register(staff_branch="")
        self.assertFalse(User.objects.filter(username="ravi").exists())

    def test_customer_registration_makes_no_request(self):
        self.register(account_type="customer", staff_branch="")
        self.assertTrue(User.objects.filter(username="ravi").exists())
        self.assertFalse(StaffRequest.objects.exists())

    def test_request_approve_and_remove(self):
        self.register()
        req = StaffRequest.objects.get()
        self.assertEqual((req.branch, req.status), (self.branch, "pending"))
        self.client.login(username="own", password="pass")
        url = reverse("workspace:staff", args=[self.branch.id])
        self.assertContains(self.client.get(url), "Ravi K")
        self.client.post(url, {"action": "approve", "request_id": req.id})
        profile = UserProfile.objects.get(user__username="ravi")
        self.assertEqual((profile.role, profile.branch, profile.organization), ("staff", self.branch, self.org))
        req.refresh_from_db()
        self.assertEqual((req.status, req.decided_by), ("approved", self.owner))
        self.client.post(url, {"action": "remove", "profile_id": profile.id})
        profile.refresh_from_db()
        self.assertEqual((profile.role, profile.branch), ("customer", None))

    def test_reject_and_other_branch_admin_cannot_approve(self):
        self.register()
        req = StaffRequest.objects.get()
        admin2 = User.objects.create_user(username="adm2", password="pass")
        UserProfile.objects.create(user=admin2, role="branch_admin", organization=self.org, branch=self.other)
        self.client.login(username="adm2", password="pass")
        self.client.post(reverse("workspace:staff", args=[self.branch.id]), {"action": "approve", "request_id": req.id})
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")
        self.client.login(username="own", password="pass")
        self.client.post(reverse("workspace:staff", args=[self.branch.id]), {"action": "reject", "request_id": req.id})
        req.refresh_from_db()
        self.assertEqual(req.status, "rejected")
        self.assertFalse(UserProfile.objects.filter(user__username="ravi", role="staff").exists())


class HighwayLocationTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org", email="o@t.com", phone="1")
        self.dhaba = Branch.objects.create(name="Sher-e-Punjab", organization=org,
                                           services_category=Service_Category.objects.create(name="Restaurant"))
        admin = User.objects.create_user(username="adm", password="pass")
        UserProfile.objects.create(user=admin, role="branch_admin", organization=org, branch=self.dhaba)
        self.client.login(username="adm", password="pass")
        self.url = reverse("workspace:highway", args=[self.dhaba.id])

    def test_add_new_highway_and_save_km(self):
        self.client.post(self.url, {"highway_choice": "new", "new_highway_name": "NH-44", "new_start_point": "Delhi",
                                    "new_end_point": "Kanyakumari", "milestone_km": "112.5", "direction_of_travel": "UP"})
        hb = HighwayBranch.objects.get(branch=self.dhaba)
        self.assertEqual((hb.highway.name, hb.milestone_km, hb.direction_of_travel), ("NH-44", Decimal("112.50"), "UP"))

    def test_pick_existing_highway_sets_segment(self):
        hw = Highway.objects.create(name="NH-48", start_point="Delhi", end_point="Mumbai")
        seg = HighwaySegment.objects.create(highway=hw, start_place="Delhi", end_place="Jaipur", start_km=0, end_km=270)
        self.client.post(self.url, {"highway_choice": str(hw.id), "milestone_km": "60", "direction_of_travel": "BOTH"})
        self.assertEqual(HighwayBranch.objects.get(branch=self.dhaba).segment, seg)
        self.client.post(self.url, {"action": "remove"})
        self.assertFalse(HighwayBranch.objects.exists())

    def test_duplicate_new_highway_rejected(self):
        Highway.objects.create(name="NH-44", start_point="Delhi", end_point="Kanyakumari")
        self.client.post(self.url, {"highway_choice": "new", "new_highway_name": "nh-44", "new_start_point": "A",
                                    "new_end_point": "B", "milestone_km": "10", "direction_of_travel": "BOTH"})
        self.assertEqual(Highway.objects.count(), 1)
        self.assertFalse(HighwayBranch.objects.exists())
