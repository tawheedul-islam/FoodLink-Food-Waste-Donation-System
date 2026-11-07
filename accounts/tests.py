from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from donations.models import FoodDonation
from requests_app.models import DonationRequest
from .models import User


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
