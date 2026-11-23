from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.models import Organization, OrganizationMembership
from donations.models import FoodDonation
from .models import DonationReceipt, DonationRequest, Notification


class PickupSchedulingTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.donor = User.objects.create_user(
            username='donor',
            password='test-password',
            role='donor',
        )
        self.receiver = User.objects.create_user(
            username='receiver',
            password='test-password',
            role='receiver',
        )
        self.pickup_start = now + timedelta(days=1)
        self.pickup_end = now + timedelta(days=2)
        self.donation = FoodDonation.objects.create(
            donor=self.donor,
            food_name='Fresh produce',
            category='raw',
            quantity='5 kg',
            expiry_time=now + timedelta(days=3),
            pickup_location='Community center',
            pickup_window_start=self.pickup_start,
            pickup_window_end=self.pickup_end,
        )
        self.client.force_login(self.receiver)

    def pickup_time_input(self, value):
        return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')

    def test_receiver_proposes_pickup_time_and_donor_confirms(self):
        pickup_time = self.pickup_start + timedelta(hours=2)
        response = self.client.post(
            reverse('create_request', args=[self.donation.pk]),
            {'pickup_time': self.pickup_time_input(pickup_time)},
        )

        self.assertRedirects(response, reverse('my_requests'))
        request = DonationRequest.objects.get(donation=self.donation)
        self.assertEqual(request.pickup_time, pickup_time.replace(second=0, microsecond=0))
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, 'requested')
        self.assertTrue(Notification.objects.filter(user=self.donor, message__contains='requested').exists())

        self.client.force_login(self.donor)
        response = self.client.post(
            reverse('update_request_status', args=[request.pk, 'accepted']),
        )

        self.assertRedirects(response, reverse('incoming_requests'))
        request.refresh_from_db()
        self.assertEqual(request.status, 'accepted')
        self.assertIsNotNone(request.accepted_at)
        self.assertTrue(Notification.objects.filter(
            user=self.receiver,
            message__contains='Pickup is confirmed',
        ).exists())

        response = self.client.post(
            reverse('update_request_status', args=[request.pk, 'completed']),
        )
        self.assertRedirects(response, reverse('incoming_requests'))
        request.refresh_from_db()
        self.assertEqual(request.status, 'completed')
        self.assertIsNotNone(request.completed_at)

    def test_rejection_is_recorded_and_shown_in_both_request_views(self):
        request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            pickup_time=self.pickup_start + timedelta(hours=2),
        )
        self.client.force_login(self.donor)
        response = self.client.post(
            reverse('update_request_status', args=[request.pk, 'rejected']),
        )

        self.assertRedirects(response, reverse('incoming_requests'))
        request.refresh_from_db()
        self.assertEqual(request.status, 'rejected')
        self.assertIsNotNone(request.rejected_at)
        self.assertContains(
            self.client.get(reverse('incoming_requests')),
            'Request declined',
        )

        self.client.force_login(self.receiver)
        self.assertContains(
            self.client.get(reverse('my_requests')),
            'Request declined',
        )

    def test_legacy_accepted_request_renders_without_timestamp(self):
        request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            status='accepted',
            pickup_time=self.pickup_start + timedelta(hours=2),
        )

        response = self.client.get(reverse('my_requests'))

        self.assertContains(response, 'Accepted (date unavailable)')
        self.assertContains(response, 'Awaiting pickup')
        self.assertEqual(request.accepted_at, None)

    def test_receiver_cannot_choose_time_outside_donor_window(self):
        outside_window = self.pickup_end + timedelta(hours=1)
        response = self.client.post(
            reverse('create_request', args=[self.donation.pk]),
            {'pickup_time': self.pickup_time_input(outside_window)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a time within the donor&#x27;s pickup availability.")
        self.assertFalse(DonationRequest.objects.exists())

    def test_get_request_page_does_not_create_request(self):
        response = self.client.get(reverse('create_request', args=[self.donation.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preferred pickup time')
        self.assertFalse(DonationRequest.objects.exists())

    def test_get_status_action_does_not_accept_request(self):
        request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            pickup_time=self.pickup_start + timedelta(hours=2),
        )
        self.client.force_login(self.donor)

        response = self.client.get(
            reverse('update_request_status', args=[request.pk, 'accepted']),
        )

        self.assertRedirects(response, reverse('incoming_requests'))
        request.refresh_from_db()
        self.assertEqual(request.status, 'pending')

    def test_receiver_can_request_on_behalf_of_workspace_and_team_can_see_it(self):
        teammate = User.objects.create_user(
            username='receiver-teammate',
            password='test-password',
            role='receiver',
        )
        organization = Organization.objects.create(
            name='Community Shelter',
            role='receiver',
            created_by=self.receiver,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.receiver,
            role=OrganizationMembership.ROLE_OWNER,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=teammate,
            role=OrganizationMembership.ROLE_MEMBER,
        )
        pickup_time = self.pickup_start + timedelta(hours=2)

        response = self.client.post(
            reverse('create_request', args=[self.donation.pk]),
            {
                'receiver_organization': organization.pk,
                'pickup_time': self.pickup_time_input(pickup_time),
            },
        )

        self.assertRedirects(response, reverse('my_requests'))
        request = DonationRequest.objects.get(donation=self.donation)
        self.assertEqual(request.receiver_organization, organization)

        self.client.force_login(teammate)
        response = self.client.get(reverse('my_requests'))
        self.assertContains(response, 'Fresh produce')
        self.assertContains(response, 'Community Shelter')

    def test_receiver_cannot_submit_request_for_donor_workspace(self):
        organization = Organization.objects.create(
            name='Donor-only kitchen',
            role='donor',
            created_by=self.donor,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.donor,
            role=OrganizationMembership.ROLE_OWNER,
        )
        pickup_time = self.pickup_start + timedelta(hours=2)

        response = self.client.post(
            reverse('create_request', args=[self.donation.pk]),
            {
                'receiver_organization': organization.pk,
                'pickup_time': self.pickup_time_input(pickup_time),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(DonationRequest.objects.exists())

    def test_receiver_confirmation_creates_a_downloadable_pdf_receipt(self):
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            pickup_time=self.pickup_start + timedelta(hours=2),
            status='completed',
            completed_at=timezone.now(),
        )

        response = self.client.post(
            reverse('confirm_receipt', args=[donation_request.pk]),
        )

        self.assertRedirects(response, reverse('my_requests'))
        receipt = DonationReceipt.objects.get(donation_request=donation_request)
        self.assertEqual(receipt.donation_name, 'Fresh produce')
        self.assertEqual(receipt.quantity, '5 kg')
        self.assertEqual(receipt.donor_name, self.donor.username)
        self.assertEqual(receipt.receiver_name, self.receiver.username)
        self.assertEqual(receipt.pickup_location, 'Community center')
        self.assertEqual(receipt.pickup_time, donation_request.pickup_time)
        self.assertTrue(Notification.objects.filter(
            user=self.donor,
            message__contains='Receipt confirmed',
        ).exists())

        download = self.client.get(
            reverse('donation_receipt', args=[donation_request.pk]),
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'application/pdf')
        self.assertIn(b'%PDF-', download.content[:10])
        self.assertIn('attachment;', download['Content-Disposition'])
        self.assertIn('private, no-store', download['Cache-Control'])

    def test_receipt_requires_completed_status_and_receiver_post(self):
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            pickup_time=self.pickup_start + timedelta(hours=2),
            status='accepted',
        )

        response = self.client.post(
            reverse('confirm_receipt', args=[donation_request.pk]),
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(DonationReceipt.objects.exists())

        donation_request.status = 'completed'
        donation_request.save(update_fields=['status'])
        response = self.client.get(
            reverse('confirm_receipt', args=[donation_request.pk]),
        )
        self.assertRedirects(response, reverse('my_requests'))
        self.assertFalse(DonationReceipt.objects.exists())

        self.client.force_login(self.donor)
        response = self.client.post(
            reverse('confirm_receipt', args=[donation_request.pk]),
        )
        self.assertRedirects(response, reverse('my_requests'))
        self.assertFalse(DonationReceipt.objects.exists())

    def test_receipt_confirmation_is_idempotent_and_pdf_uses_snapshot(self):
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            status='completed',
            completed_at=timezone.now(),
        )
        url = reverse('confirm_receipt', args=[donation_request.pk])
        self.client.post(url)
        original_receipt = DonationReceipt.objects.get(donation_request=donation_request)
        original_number = original_receipt.receipt_number

        self.donation.food_name = 'Changed after handover'
        self.donation.save(update_fields=['food_name'])
        response = self.client.post(url)

        self.assertRedirects(response, reverse('my_requests'))
        self.assertEqual(DonationReceipt.objects.filter(donation_request=donation_request).count(), 1)
        original_receipt.refresh_from_db()
        self.assertEqual(original_receipt.receipt_number, original_number)
        self.assertEqual(original_receipt.donation_name, 'Fresh produce')
        self.assertEqual(
            Notification.objects.filter(user=self.donor, message__contains='Receipt confirmed').count(),
            1,
        )

    def test_only_donation_participants_can_download_receipt(self):
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.post(reverse('confirm_receipt', args=[donation_request.pk]))
        outsider = User.objects.create_user(
            username='receipt-outsider',
            password='test-password',
            role='receiver',
        )
        self.client.force_login(outsider)

        response = self.client.get(
            reverse('donation_receipt', args=[donation_request.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_participating_workspace_members_can_download_receipt(self):
        donor_teammate = User.objects.create_user(
            username='donor-receipt-member',
            password='test-password',
            role='donor',
        )
        receiver_teammate = User.objects.create_user(
            username='receiver-receipt-member',
            password='test-password',
            role='receiver',
        )
        donor_organization = Organization.objects.create(
            name='Donor receipt team',
            role='donor',
            created_by=self.donor,
        )
        receiver_organization = Organization.objects.create(
            name='Receiver receipt team',
            role='receiver',
            created_by=self.receiver,
        )
        for organization, owner, member in (
            (donor_organization, self.donor, donor_teammate),
            (receiver_organization, self.receiver, receiver_teammate),
        ):
            OrganizationMembership.objects.create(
                organization=organization,
                user=owner,
                role=OrganizationMembership.ROLE_OWNER,
            )
            OrganizationMembership.objects.create(
                organization=organization,
                user=member,
                role=OrganizationMembership.ROLE_MEMBER,
            )

        self.donation.organization = donor_organization
        self.donation.save(update_fields=['organization'])
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            receiver_organization=receiver_organization,
            status='completed',
            completed_at=timezone.now(),
        )
        self.client.post(reverse('confirm_receipt', args=[donation_request.pk]))
        receipt_url = reverse('donation_receipt', args=[donation_request.pk])

        self.client.force_login(donor_teammate)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)

        self.client.force_login(receiver_teammate)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)
