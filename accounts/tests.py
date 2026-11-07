from datetime import timedelta
from unittest.mock import Mock

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import UserAdmin, VerificationRequestAdmin
from .forms import ProfileEditForm
from .models import User, VerificationRequest
from donations.models import FoodDonation
from requests_app.models import DonationRequest


class DashboardImpactTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='impact-donor',
            password='test-password',
            role='donor',
        )
        self.other_donor = User.objects.create_user(
            username='other-impact-donor',
            password='test-password',
            role='donor',
        )
        self.receiver = User.objects.create_user(
            username='impact-receiver',
            password='test-password',
            role='receiver',
        )
        self.other_receiver = User.objects.create_user(
            username='other-impact-receiver',
            password='test-password',
            role='receiver',
        )

        first_donation = self.create_donation(self.donor, 'First completed donation')
        second_donation = self.create_donation(self.other_donor, 'Second completed donation')
        self.create_request(first_donation, self.receiver, 'completed')
        self.create_request(second_donation, self.other_receiver, 'completed')
        self.create_request(
            self.create_donation(self.donor, 'Pending donation'),
            self.other_receiver,
            'pending',
        )

    def create_donation(self, donor, food_name):
        return FoodDonation.objects.create(
            donor=donor,
            food_name=food_name,
            category='raw',
            quantity='2 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Community center',
            status='completed',
        )

    def create_request(self, donation, receiver, status):
        return DonationRequest.objects.create(
            donation=donation,
            receiver=receiver,
            status=status,
        )

    def test_donor_dashboard_shows_personal_and_community_impact(self):
        self.client.force_login(self.donor)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['personal_completed_count'], 1)
        self.assertEqual(response.context['community_completed_donations'], 2)
        self.assertEqual(response.context['community_donors'], 2)
        self.assertEqual(response.context['community_receivers'], 2)
        self.assertContains(response, 'of your donations completed')
        self.assertContains(response, 'Donations completed')

    def test_receiver_dashboard_shows_personal_and_community_impact(self):
        self.client.force_login(self.receiver)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['personal_completed_count'], 1)
        self.assertEqual(response.context['community_completed_donations'], 2)
        self.assertEqual(response.context['community_donors'], 2)
        self.assertEqual(response.context['community_receivers'], 2)
        self.assertContains(response, 'of your pickups completed')


class UserVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='verification-user',
            password='test-password',
            role='donor',
        )

    def test_profile_edit_form_does_not_allow_self_verification(self):
        form = ProfileEditForm(
            data={
                'first_name': 'Verified',
                'last_name': 'User',
                'email': '',
                'phone_number': '01712345678',
                'address': '',
                'is_verified': 'on',
            },
            instance=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated_user = form.save()
        self.assertFalse(updated_user.is_verified)
        self.assertIsNone(updated_user.verified_at)

    def test_admin_verification_sets_and_clears_timestamp(self):
        user_admin = UserAdmin(User, AdminSite())
        request = RequestFactory().post('/admin/accounts/user/')

        self.user.is_verified = True
        user_admin.save_model(
            request,
            self.user,
            form=type('Form', (), {'initial': {}})(),
            change=False,
        )
        self.assertIsNotNone(self.user.verified_at)

        self.user.is_verified = False
        user_admin.save_model(
            request,
            self.user,
            form=type('Form', (), {'initial': {'is_verified': True}})(),
            change=True,
        )
        self.assertIsNone(self.user.verified_at)

    def test_dashboard_and_profile_pages_show_admin_verification(self):
        self.user.is_verified = True
        self.user.verified_at = timezone.now()
        self.user.save()
        self.client.force_login(self.user)

        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'FoodLink verified')

        profile = self.client.get(reverse('profile_edit'))
        self.assertNotContains(profile, 'is_verified')


class VerificationRequestWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='applicant',
            password='test-password',
            role='donor',
            email='applicant@example.com',
        )
        self.admin_user = User.objects.create_superuser(
            username='review-admin',
            password='test-password',
            email='admin@example.com',
        )
        self.client.force_login(self.user)
        self.data = {
            'organization_name': 'Community Food Center',
            'organization_type': 'Community kitchen',
            'organization_website': 'https://example.org',
            'organization_summary': 'We distribute surplus food to local families.',
        }

    def test_user_can_submit_verification_request(self):
        response = self.client.post(reverse('verification_request'), self.data)

        self.assertRedirects(response, reverse('dashboard'))
        verification_request = VerificationRequest.objects.get(user=self.user)
        self.assertEqual(verification_request.status, VerificationRequest.STATUS_PENDING)
        self.assertEqual(verification_request.organization_name, 'Community Food Center')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_user_cannot_submit_duplicate_pending_request(self):
        first_response = self.client.post(reverse('verification_request'), self.data)
        second_response = self.client.post(reverse('verification_request'), self.data)

        self.assertRedirects(first_response, reverse('dashboard'))
        self.assertRedirects(second_response, reverse('dashboard'))
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 1)

    def test_declined_request_can_be_resubmitted(self):
        old_request = VerificationRequest.objects.create(
            user=self.user,
            organization_name='Earlier organization',
            organization_type='Community group',
            organization_summary='An earlier application.',
            status=VerificationRequest.STATUS_DECLINED,
            reviewed_by=self.admin_user,
            reviewed_at=timezone.now(),
        )

        response = self.client.post(reverse('verification_request'), self.data)

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 2)
        old_request.refresh_from_db()
        self.assertEqual(old_request.status, VerificationRequest.STATUS_DECLINED)

    def test_verified_user_cannot_apply_again(self):
        self.user.is_verified = True
        self.user.verified_at = timezone.now()
        self.user.save()

        response = self.client.post(reverse('verification_request'), self.data)

        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(VerificationRequest.objects.filter(user=self.user).exists())

    def test_admin_can_approve_request_and_verify_user(self):
        verification_request = VerificationRequest.objects.create(
            user=self.user,
            organization_name='Community Food Center',
            organization_type='Community kitchen',
            organization_summary='We distribute surplus food.',
        )
        request = RequestFactory().post('/admin/accounts/verificationrequest/')
        request.user = self.admin_user
        request._messages = Mock()
        request._messages.add = Mock()
        verification_admin = VerificationRequestAdmin(VerificationRequest, AdminSite())

        verification_admin.approve_requests(
            request,
            VerificationRequest.objects.filter(pk=verification_request.pk),
        )

        verification_request.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(verification_request.status, VerificationRequest.STATUS_APPROVED)
        self.assertEqual(verification_request.reviewed_by, self.admin_user)
        self.assertIsNotNone(verification_request.reviewed_at)
        self.assertTrue(self.user.is_verified)
        self.assertEqual(self.user.verified_at, verification_request.reviewed_at)

    def test_admin_can_decline_with_note_without_verifying_user(self):
        verification_request = VerificationRequest.objects.create(
            user=self.user,
            organization_name='Community Food Center',
            organization_type='Community kitchen',
            organization_summary='We distribute surplus food.',
            review_note='Please provide more organization details.',
        )
        request = RequestFactory().post('/admin/accounts/verificationrequest/')
        request.user = self.admin_user
        request._messages = Mock()
        request._messages.add = Mock()
        verification_admin = VerificationRequestAdmin(VerificationRequest, AdminSite())

        verification_admin.decline_requests(
            request,
            VerificationRequest.objects.filter(pk=verification_request.pk),
        )

        verification_request.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(verification_request.status, VerificationRequest.STATUS_DECLINED)
        self.assertEqual(verification_request.review_note, 'Please provide more organization details.')
        self.assertEqual(verification_request.reviewed_by, self.admin_user)
        self.assertFalse(self.user.is_verified)

    def test_dashboard_shows_pending_and_declined_request_status(self):
        VerificationRequest.objects.create(
            user=self.user,
            organization_name='Community Food Center',
            organization_type='Community kitchen',
            organization_summary='We distribute surplus food.',
        )

        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'awaiting admin review')
        self.assertNotContains(dashboard, 'Request verification')

        pending = VerificationRequest.objects.get(user=self.user)
        pending.status = VerificationRequest.STATUS_DECLINED
        pending.reviewed_at = timezone.now()
        pending.reviewed_by = self.admin_user
        pending.review_note = 'Please provide more organization details.'
        pending.save()

        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'was declined')
        self.assertContains(dashboard, 'Submit another request')
        self.assertContains(dashboard, 'Please provide more organization details.')
