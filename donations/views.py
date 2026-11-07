import math
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.urls import reverse
from .models import FoodDonation
from .forms import FoodDonationForm
from requests_app.models import DonationRequest
from django.utils import timezone

DISTANCE_SESSION_KEY = 'donation_search_location'
RADIUS_CHOICES = (5, 10, 25, 50, 100)


def donations_with_trust_signals():
    return FoodDonation.objects.select_related('donor').annotate(
        donor_completed_donations=Count(
            'donor__donations',
            filter=Q(donor__donations__status='completed'),
            distinct=True,
        ),
        donor_average_rating=Avg('donor__ratings_received__score'),
        donor_rating_count=Count('donor__ratings_received', distinct=True),
    )


def _distance_km(latitude, longitude, target_latitude, target_longitude):
    earth_radius_km = 6371
    latitude_delta = math.radians(target_latitude - latitude)
    longitude_delta = math.radians(target_longitude - longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(math.radians(latitude))
        * math.cos(math.radians(target_latitude))
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(min(1, haversine)))

@login_required
def donation_list(request):
    if request.user.role == 'donor':
        donations = donations_with_trust_signals().filter(donor=request.user).order_by('-created_at')
    else:
       donations = donations_with_trust_signals().filter(
           status='posted',
           expiry_time__gt=timezone.now(),
       ).order_by('-created_at')

    # Search by food name
    query = request.GET.get('q')
    if query:
        donations = donations.filter(food_name__icontains=query)

    # Filter by category
    category = request.GET.get('category')
    if category:
        donations = donations.filter(category=category)

    # Filter by location
    location = request.GET.get('location')
    if location:
        donations = donations.filter(pickup_location__icontains=location)
        
    radius = request.GET.get('radius', '25')
    if radius not in {str(value) for value in RADIUS_CHOICES}:
        radius = '25'
        messages.warning(request, 'Invalid distance filter. Showing donations within 25 km.')

    search_location = request.session.get(DISTANCE_SESSION_KEY)
    unlocated_count = 0
    if request.user.role == 'receiver' and search_location:
        latitude = float(search_location['latitude'])
        longitude = float(search_location['longitude'])
        radius_km = int(radius)
        donations = list(donations)
        unlocated_count = sum(
            donation.pickup_latitude is None or donation.pickup_longitude is None
            for donation in donations
        )
        donations_with_distance = []
        for donation in donations:
            if donation.pickup_latitude is None or donation.pickup_longitude is None:
                continue
            distance = _distance_km(
                latitude,
                longitude,
                float(donation.pickup_latitude),
                float(donation.pickup_longitude),
            )
            if distance <= radius_km:
                donation.distance_km = distance
                donations_with_distance.append(donation)
        donations = sorted(donations_with_distance, key=lambda donation: donation.distance_km)

    paginator = Paginator(donations, 6)
    page_number = request.GET.get('page')
    donations = paginator.get_page(page_number)

    context = {
        'donations': donations,
        'category_choices': FoodDonation.CATEGORY_CHOICES,
        'selected_category': category,
        'query': query or '',
        'location': location or '',
        'radius': radius,
        'radius_choices': RADIUS_CHOICES,
        'has_search_location': bool(search_location) and request.user.role == 'receiver',
        'unlocated_count': unlocated_count,
    }
    return render(request, 'donations/donation_list.html', context)


@login_required
def donation_location(request):
    if request.user.role != 'receiver':
        messages.error(request, 'Only receivers can use nearby donation search.')
        return redirect('donation_list')
    if request.method != 'POST':
        messages.error(request, 'Use the location controls to update nearby search.')
        return redirect('donation_list')

    action = request.POST.get('action')
    if action == 'clear':
        request.session.pop(DISTANCE_SESSION_KEY, None)
        messages.success(request, 'Your search location was cleared.')
    elif action == 'set':
        try:
            latitude = Decimal(request.POST.get('latitude', ''))
            longitude = Decimal(request.POST.get('longitude', ''))
        except (InvalidOperation, TypeError):
            messages.error(request, 'Could not read your location. Please try again.')
            return redirect('donation_list')

        if not latitude.is_finite() or not longitude.is_finite() or not (
            Decimal('-90') <= latitude <= Decimal('90')
            and Decimal('-180') <= longitude <= Decimal('180')
        ):
            messages.error(request, 'The location coordinates are invalid. Please try again.')
            return redirect('donation_list')

        request.session[DISTANCE_SESSION_KEY] = {
            'latitude': str(latitude),
            'longitude': str(longitude),
        }
        messages.success(request, 'Nearby search is on. Your location is saved only in this session.')
    else:
        messages.error(request, 'Invalid location action.')
        return redirect('donation_list')

    preserved_filters = {
        key: request.POST.get(key, request.GET.get(key, ''))
        for key in ('q', 'category', 'location', 'radius')
        if request.POST.get(key, request.GET.get(key, ''))
    }
    query = urlencode(preserved_filters)
    return redirect(f"{reverse('donation_list')}{'?' + query if query else ''}")


@login_required
def donation_create(request):
    if request.user.role != 'donor':
        messages.error(request, 'Only donors can post food donations.')
        return redirect('donation_list')

    if request.method == 'POST':
        form = FoodDonationForm(request.POST , request.FILES)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.donor = request.user
            donation.save()
            messages.success(request, 'Food donation posted successfully!')
            return redirect('donation_list')
    else:
        form = FoodDonationForm()
    return render(request, 'donations/donation_form.html', {'form': form})

@login_required
def donation_detail(request, pk):
    donation = get_object_or_404(donations_with_trust_signals(), pk=pk)
    donation_requests = None
    if donation.donor == request.user:
        donation_requests = DonationRequest.objects.filter(
            donation=donation
        ).select_related('receiver').annotate(
            receiver_completed_pickups=Count(
                'receiver__requests',
                filter=Q(receiver__requests__status='completed'),
                distinct=True,
            ),
        ).order_by('-request_date')
    return render(request, 'donations/donation_detail.html', {
        'donation': donation,
        'donation_requests': donation_requests
    })

@login_required
def donation_edit(request, pk):
    donation = get_object_or_404(FoodDonation, pk=pk)

    if donation.donor != request.user:
        messages.error(request, 'You are not allowed to edit this donation.')
        return redirect('donation_list')

    if request.method == 'POST':
        form = FoodDonationForm(request.POST, request.FILES, instance=donation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Donation updated successfully!')
            return redirect('donation_detail', pk=pk)
    else:
        form = FoodDonationForm(instance=donation)
    return render(request, 'donations/donation_form.html', {'form': form, 'editing': True})

@login_required
def donation_delete(request, pk):
    donation = get_object_or_404(FoodDonation, pk=pk)

    if donation.donor != request.user:
        messages.error(request, 'You are not allowed to delete this donation.')
        return redirect('donation_list')

    if request.method == 'POST':
        donation.delete()
        messages.success(request, 'Donation deleted successfully.')
        return redirect('donation_list')

    return render(request, 'donations/donation_confirm_delete.html', {'donation': donation})