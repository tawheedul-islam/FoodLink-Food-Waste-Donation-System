from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import Organization, OrganizationMembership, User
from requests_app.models import DonationRequest, Rating
from .forms import FoodDonationForm
from .models import FoodDonation


class DonorTrustSignalTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='trusted-donor',
            password='test-password',
            role='donor',
            is_verified=True,
        )
        self.receiver = User.objects.create_user(
            username='trust-receiver',
            password='test-password',
            role='receiver',
        )
        completed_donation = FoodDonation.objects.create(
            donor=self.donor,
            food_name='Past donation',
            category='raw',
            quantity='1 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Community center',
            status='completed',
        )
        completed_request = DonationRequest.objects.create(
            donation=completed_donation,
            receiver=self.receiver,
            status='completed',
        )
        Rating.objects.create(
            donation_request=completed_request,
            rated_by=self.receiver,
            rated_user=self.donor,
            score=5,
        )
        self.available_donation = FoodDonation.objects.create(
            donor=self.donor,
            food_name='Available fruit',
            category='raw',
            quantity='2 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Community center',
        )
        self.client.force_login(self.receiver)

    def test_donation_listing_shows_verified_badge_rating_and_completed_count(self):
        response = self.client.get(reverse('donation_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FoodLink verified')
        self.assertContains(response, '1 completed')
        self.assertContains(response, '5.0')

    def test_donation_detail_shows_donor_trust_signals(self):
        response = self.client.get(
            reverse('donation_detail', args=[self.available_donation.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FoodLink verified')
        self.assertContains(response, '1 completed donation')
        self.assertContains(response, '5.0 from 1 review')


class OrganizationDonationAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='org-donor-owner',
            password='test-password',
            role='donor',
        )
        self.member = User.objects.create_user(
            username='org-donor-member',
            password='test-password',
            role='donor',
        )
        self.outsider = User.objects.create_user(
            username='org-donor-outsider',
            password='test-password',
            role='donor',
        )
        self.receiver = User.objects.create_user(
            username='org-donation-receiver',
            password='test-password',
            role='receiver',
        )
        self.organization = Organization.objects.create(
            name='Shared Kitchen',
            role='donor',
            created_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.ROLE_OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role=OrganizationMembership.ROLE_MEMBER,
        )
        self.donation = FoodDonation.objects.create(
            donor=self.owner,
            organization=self.organization,
            food_name='Team surplus',
            category='raw',
            quantity='3 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Shared Kitchen',
        )

    def test_member_can_see_and_manage_workspace_donation(self):
        self.client.force_login(self.member)

        listing = self.client.get(reverse('donation_list'))
        self.assertContains(listing, 'Team surplus')
        self.assertContains(listing, 'Shared Kitchen')

        detail = self.client.get(reverse('donation_detail', args=[self.donation.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.context['can_manage_donation'])

        edit = self.client.get(reverse('donation_edit', args=[self.donation.pk]))
        self.assertEqual(edit.status_code, 200)

    def test_member_can_post_donation_for_workspace(self):
        now = timezone.localtime()
        self.client.force_login(self.member)

        response = self.client.post(
            reverse('donation_create'),
            {
                'organization': self.organization.pk,
                'food_name': 'Member surplus',
                'category': 'raw',
                'quantity': '2 kg',
                'description': '',
                'allergen_info': '',
                'storage_instructions': '',
                'packaging_info': '',
                'preparation_time': '',
                'expiry_time': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
                'pickup_location': 'Shared Kitchen',
                'pickup_latitude': '',
                'pickup_longitude': '',
                'pickup_window_start': (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
                'pickup_window_end': (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertRedirects(response, reverse('donation_list'))
        donation = FoodDonation.objects.get(food_name='Member surplus')
        self.assertEqual(donation.donor, self.member)
        self.assertEqual(donation.organization, self.organization)

    def test_non_member_cannot_manage_workspace_donation(self):
        self.client.force_login(self.outsider)

        listing = self.client.get(reverse('donation_list'))
        self.assertNotContains(listing, 'Team surplus')

        detail = self.client.get(reverse('donation_detail', args=[self.donation.pk]))
        self.assertFalse(detail.context['can_manage_donation'])

        edit = self.client.get(reverse('donation_edit', args=[self.donation.pk]))
        self.assertRedirects(edit, reverse('donation_list'))

    def test_workspace_member_can_process_incoming_request(self):
        donation_request = DonationRequest.objects.create(
            donation=self.donation,
            receiver=self.receiver,
            pickup_time=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.member)

        incoming = self.client.get(reverse('incoming_requests'))
        self.assertContains(incoming, 'Team surplus')

        response = self.client.post(
            reverse('update_request_status', args=[donation_request.pk, 'accepted']),
        )

        self.assertRedirects(response, reverse('incoming_requests'))
        donation_request.refresh_from_db()
        self.assertEqual(donation_request.status, 'accepted')


class NearbyDonationTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='nearby-donor',
            password='test-password',
            role='donor',
        )
        self.receiver = User.objects.create_user(
            username='nearby-receiver',
            password='test-password',
            role='receiver',
        )
        self.client.force_login(self.receiver)

    def create_donation(self, name, latitude=None, longitude=None):
        return FoodDonation.objects.create(
            donor=self.donor,
            food_name=name,
            category='raw',
            quantity='2 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Community center',
            pickup_latitude=latitude,
            pickup_longitude=longitude,
        )

    def test_receiver_can_set_location_and_sort_donations_by_distance(self):
        self.create_donation('Closer apples', '0.010000', '0.000000')
        self.create_donation('Farther pears', '0.020000', '0.000000')
        self.create_donation('Unlocated bread')

        response = self.client.post(
            f"{reverse('donation_location')}?q=rice&radius=10",
            {'action': 'set', 'latitude': '0.000', 'longitude': '0.000'},
        )

        self.assertRedirects(response, f"{reverse('donation_list')}?q=rice&radius=10")
        self.assertEqual(
            self.client.session['donation_search_location'],
            {'latitude': '0.000', 'longitude': '0.000'},
        )
        response = self.client.get(reverse('donation_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nearby search is on')
        self.assertContains(response, '1.1 km away')
        donations = list(response.context['donations'])
        self.assertEqual([donation.food_name for donation in donations], [
            'Closer apples',
            'Farther pears',
        ])
        self.assertAlmostEqual(donations[0].distance_km, 1.11, places=1)
        self.assertEqual(response.context['unlocated_count'], 1)

    def test_nearby_radius_excludes_donations_outside_selected_distance(self):
        self.create_donation('Nearby apples', '0.010000', '0.000000')
        self.create_donation('Distant pears', '0.100000', '0.000000')
        self.client.post(
            reverse('donation_location'),
            {'action': 'set', 'latitude': '0.000', 'longitude': '0.000'},
        )

        response = self.client.get(reverse('donation_list'), {'radius': '5'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [donation.food_name for donation in response.context['donations']],
            ['Nearby apples'],
        )

    def test_invalid_or_non_receiver_location_is_rejected(self):
        response = self.client.post(
            reverse('donation_location'),
            {'action': 'set', 'latitude': '91', 'longitude': '0'},
        )
        self.assertRedirects(response, reverse('donation_list'))
        self.assertNotIn('donation_search_location', self.client.session)

        self.client.force_login(self.donor)
        response = self.client.post(
            reverse('donation_location'),
            {'action': 'set', 'latitude': '0', 'longitude': '0'},
        )
        self.assertRedirects(response, reverse('donation_list'))
        self.assertNotIn('donation_search_location', self.client.session)

    def test_receiver_can_clear_saved_search_location(self):
        self.client.post(
            reverse('donation_location'),
            {'action': 'set', 'latitude': '0.000', 'longitude': '0.000'},
        )

        response = self.client.post(
            reverse('donation_location'),
            {'action': 'clear'},
        )

        self.assertRedirects(response, reverse('donation_list'))
        self.assertNotIn('donation_search_location', self.client.session)


class DonationFoodSafetyTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='food-donor',
            password='test-password',
            role='donor',
        )

    def test_safety_details_are_saved_and_available_to_receivers(self):
        now = timezone.localtime()
        data = {
            'food_name': 'Vegetable curry',
            'category': 'cooked',
            'quantity': '4 portions',
            'allergen_info': 'Contains peanuts',
            'storage_instructions': 'Keep refrigerated',
            'packaging_info': 'Sealed containers',
            'preparation_time': '',
            'expiry_time': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'pickup_location': 'Community center',
            'pickup_window_start': (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'pickup_window_end': (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
        }
        form = FoodDonationForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        donation = form.save(commit=False)
        donation.donor = self.donor
        donation.save()

        self.assertEqual(donation.allergen_info, 'Contains peanuts')
        self.assertEqual(donation.storage_instructions, 'Keep refrigerated')
        self.assertEqual(donation.packaging_info, 'Sealed containers')

    def test_safety_details_are_optional_for_existing_donations(self):
        donation = FoodDonation.objects.create(
            donor=self.donor,
            food_name='Fresh apples',
            category='raw',
            quantity='2 kg',
            expiry_time=timezone.now() + timedelta(days=2),
            pickup_location='Community center',
        )

        self.assertEqual(donation.allergen_info, '')
        self.assertEqual(donation.storage_instructions, '')
        self.assertEqual(donation.packaging_info, '')

    def test_donation_form_requires_both_pickup_coordinates_together(self):
        now = timezone.localtime()
        data = {
            'food_name': 'Fresh oranges',
            'category': 'raw',
            'quantity': '2 kg',
            'preparation_time': '',
            'expiry_time': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'pickup_location': 'Community center',
            'pickup_latitude': '22.3569',
            'pickup_longitude': '',
            'pickup_window_start': (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'pickup_window_end': (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
        }

        form = FoodDonationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn('pickup_latitude', form.errors)
        self.assertIn('pickup_longitude', form.errors)
