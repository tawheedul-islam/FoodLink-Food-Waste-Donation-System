from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from donations.models import FoodDonation
from .models import DonationRequest, Notification


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
        self.assertTrue(Notification.objects.filter(
            user=self.receiver,
            message__contains='Pickup is confirmed',
        ).exists())

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
