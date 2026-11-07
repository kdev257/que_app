import datetime
import json
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from login.models import Guest, User, UserProfile
from organization.models import Branch, Organization
from queues.models import Token
from .models import BreachIncident, ConsentRecord, DataRequest, ErasureNotice, PrivacyNotice, ProcessingLog
from .services import anonymise_user, notify_breach, record_consent


class NoticeAndConsentTests(TestCase):
    def test_initial_notice_exists_and_page_shows(self):
        self.assertIsNotNone(PrivacyNotice.current())
        response = self.client.get(reverse("privacy:notice"))
        self.assertContains(response, "Your rights")

    def test_registration_requires_age_and_consent_ticks(self):
        data = {"username": "newuser", "first_name": "A", "last_name": "B", "email": "a@b.com",
                "password1": "S3cure-pass-123", "password2": "S3cure-pass-123"}
        self.client.post(reverse("register"), data)
        self.assertFalse(User.objects.filter(username="newuser").exists())

        data.update({"age_confirm": "on", "accept_notice": "on"})
        self.client.post(reverse("register"), data)
        user = User.objects.get(username="newuser")
        consent = ConsentRecord.objects.get(user=user)
        self.assertTrue(consent.age_confirmed)
        self.assertEqual(consent.notice, PrivacyNotice.current())

    def test_guest_login_records_consent(self):
        data = {"name": "G", "email": "g@t.com", "phone_no": "999", "pin_code": "110001",
                "age_confirm": "on", "accept_notice": "on"}
        self.client.post(reverse("guest_login"), data)
        guest = Guest.objects.get(email="g@t.com")
        self.assertTrue(ConsentRecord.objects.filter(guest=guest).exists())
        self.assertTrue(ProcessingLog.objects.filter(action="guest_login", subject_guest=guest).exists())

    @override_settings(DPDP_ENFORCE_CONSENT=True)
    def test_old_user_without_consent_is_asked(self):
        User.objects.create_user(username="old", password="pass")
        self.client.login(username="old", password="pass")
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("privacy:consent"), response.url)

        self.client.post(reverse("privacy:consent"), {"age_confirm": "on", "accept_notice": "on"})
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)

    @override_settings(DPDP_ENFORCE_CONSENT=True)
    def test_new_notice_version_asks_again(self):
        user = User.objects.create_user(username="u", password="pass")
        record_consent(None, user=user)
        PrivacyNotice.objects.create(version="2.0", body="New text", is_current=True)
        self.client.login(username="u", password="pass")
        response = self.client.get(reverse("index"))
        self.assertIn(reverse("privacy:consent"), response.url)


class RightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cust", password="pass", email="c@t.com", first_name="Cee")
        UserProfile.objects.create(user=self.user, role="customer", phone_no="98765", pin_code="110001")
        record_consent(None, user=self.user)
        self.client.login(username="cust", password="pass")

    def test_download_my_data(self):
        response = self.client.get(reverse("privacy:export_data"))
        data = json.loads(response.content)
        self.assertEqual(data["account"]["email"], "c@t.com")
        self.assertEqual(data["profile"]["phone_no"], "98765")
        self.assertTrue(ProcessingLog.objects.filter(action="data_exported").exists())

    def test_grievance_request_gets_reference_and_due_date(self):
        self.client.post(reverse("privacy:my_data"), {"request_type": "grievance", "details": "Wrong data"})
        req = DataRequest.objects.get(user=self.user)
        self.assertTrue(req.reference.startswith("DPR-"))
        self.assertEqual(req.due_date, req.created_at.date() + datetime.timedelta(days=90))
        self.assertEqual(len(mail.outbox), 1)

    def test_delete_account_locks_and_schedules_erasure(self):
        self.client.post(reverse("privacy:delete_account"), {"confirm_text": "DELETE"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        req = DataRequest.objects.get(user=self.user, request_type="erasure")
        self.assertIsNotNone(req.erase_after)
        self.assertTrue(ConsentRecord.objects.filter(user=self.user, withdrawn_at__isnull=False).exists())

    def test_delete_blocked_with_active_booking(self):
        org = Organization.objects.create(name="O", email="o@t.com", phone="1")
        branch = Branch.objects.create(name="B", organization=org)
        Token.objects.create(branch=branch, user=self.user, status="waiting")
        self.client.post(reverse("privacy:delete_account"), {"confirm_text": "DELETE"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_public_grievance_form(self):
        self.client.logout()
        self.client.post(reverse("privacy:grievance"),
                         {"contact_name": "X", "contact_email": "x@t.com", "details": "Spam"})
        self.assertTrue(DataRequest.objects.filter(contact_email="x@t.com", request_type="grievance").exists())


class RetentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sleepy", password="pass", email="s@t.com")
        UserProfile.objects.create(user=self.user, role="customer", phone_no="111", pin_code="110001")
        old = timezone.now() - datetime.timedelta(days=400)
        User.objects.filter(pk=self.user.pk).update(date_joined=old, last_login=old)
        self.user.refresh_from_db()

    def test_notice_then_anonymise_after_48_hours(self):
        call_command("dpdp_retention", stdout=StringIO())
        notice = ErasureNotice.objects.get(user=self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "sleepy")  # not yet

        ErasureNotice.objects.filter(pk=notice.pk).update(
            notified_at=timezone.now() - datetime.timedelta(hours=49),
            erase_on_or_after=timezone.now() - datetime.timedelta(hours=1),
        )
        call_command("dpdp_retention", stdout=StringIO())
        self.user.refresh_from_db()
        self.assertTrue(self.user.username.startswith("deleted_"))
        self.assertEqual(self.user.email, "")
        self.assertEqual(self.user.user_profile.phone_no, None)

    def test_active_user_is_not_touched(self):
        User.objects.filter(pk=self.user.pk).update(last_login=timezone.now())
        call_command("dpdp_retention", stdout=StringIO())
        self.assertFalse(ErasureNotice.objects.exists())

    def test_staff_are_not_anonymised(self):
        self.user.user_profile.role = "staff"
        self.user.user_profile.save()
        call_command("dpdp_retention", stdout=StringIO())
        self.assertFalse(ErasureNotice.objects.exists())

    def test_old_logs_deleted_recent_kept(self):
        ProcessingLog.objects.create(action="login")
        old = ProcessingLog.objects.create(action="login")
        ProcessingLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - datetime.timedelta(days=400))
        call_command("dpdp_retention", stdout=StringIO())
        self.assertFalse(ProcessingLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(ProcessingLog.objects.filter(action="login").exists())


class BreachTests(TestCase):
    def test_breach_notice_emails_affected_users(self):
        org = Organization.objects.create(name="O", email="o@t.com", phone="1")
        branch = Branch.objects.create(name="B", organization=org)
        other = Branch.objects.create(name="C", organization=org)
        hit = User.objects.create_user(username="hit", password="p", email="hit@t.com")
        safe = User.objects.create_user(username="safe", password="p", email="safe@t.com")
        Token.objects.create(branch=branch, user=hit)
        Token.objects.create(branch=other, user=safe)

        incident = BreachIncident.objects.create(title="Leak", nature_and_extent="Test")
        incident.affected_branches.add(branch)
        self.assertEqual(incident.board_report_due, incident.detected_at + datetime.timedelta(hours=72))

        sent = notify_breach(incident)
        self.assertEqual(sent, 1)
        self.assertEqual(mail.outbox[0].to, ["hit@t.com"])
        incident.refresh_from_db()
        self.assertEqual(incident.users_notified_count, 1)
