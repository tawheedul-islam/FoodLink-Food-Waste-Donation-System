from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from donations.models import FoodDonation
from .forms import PickupRequestForm, RatingForm
from .models import DonationRequest, Notification, Rating

@login_required
def create_request(request, pk):
    donation = get_object_or_404(FoodDonation, pk=pk)

    if request.user.role != 'receiver':
        messages.error(request, 'Only receivers can request donations.')
        return redirect('donation_detail', pk=pk)

    already_requested = DonationRequest.objects.filter(donation=donation, receiver=request.user).exists()
    if already_requested:
        messages.warning(request, 'You have already requested this donation.')
        return redirect('donation_detail', pk=pk)
    if donation.status != 'posted' or donation.expiry_time <= timezone.now():
        messages.error(request, 'This donation is no longer available to request.')
        return redirect('donation_detail', pk=pk)

    if request.method == 'POST':
        form = PickupRequestForm(request.POST, donation=donation)
        if form.is_valid():
            pickup_request = DonationRequest.objects.create(
                donation=donation,
                receiver=request.user,
                pickup_time=form.cleaned_data['pickup_time'],
            )
            donation.status = 'requested'
            donation.save(update_fields=['status'])

            local_pickup_time = timezone.localtime(pickup_request.pickup_time)
            Notification.objects.create(
                user=donation.donor,
                message=(
                    f"{request.user.username} requested '{donation.food_name}' "
                    f"for pickup at {local_pickup_time:%d %b %Y, %H:%M}."
                ),
                donation=donation,
            )
            messages.success(request, 'Pickup request submitted. The donor will confirm your time.')
            return redirect('my_requests')
    else:
        form = PickupRequestForm(donation=donation)

    return render(request, 'requests_app/create_request.html', {
        'form': form,
        'donation': donation,
    })

@login_required
def my_requests(request):
    reqs = DonationRequest.objects.filter(receiver=request.user).order_by('-request_date')
    return render(request, 'requests_app/my_requests.html', {'requests': reqs})

@login_required
def incoming_requests(request):
    if request.user.role != 'donor':
        messages.error(request, 'Only donors can view incoming requests.')
        return redirect('donation_list')
    reqs = DonationRequest.objects.filter(donation__donor=request.user).order_by('-request_date')
    return render(request, 'requests_app/incoming_requests.html', {'requests': reqs})

@login_required
def update_request_status(request, pk, new_status):
    if request.method != 'POST':
        messages.error(request, 'Use the request actions to update its status.')
        return redirect('incoming_requests')

    if new_status not in {'accepted', 'rejected', 'completed'}:
        messages.error(request, 'Invalid request status.')
        return redirect('incoming_requests')

    req = get_object_or_404(DonationRequest, pk=pk, donation__donor=request.user)
    if (new_status in {'accepted', 'rejected'} and req.status != 'pending') or (
        new_status == 'completed' and req.status != 'accepted'
    ):
        messages.error(request, 'This request can no longer be updated to that status.')
        return redirect('incoming_requests')
    if new_status == 'accepted' and req.pickup_time and req.pickup_time <= timezone.now():
        messages.error(request, 'The proposed pickup time has passed. Ask the receiver to submit a new request.')
        return redirect('incoming_requests')

    req.status = new_status
    status_time_field = {
        'accepted': 'accepted_at',
        'rejected': 'rejected_at',
        'completed': 'completed_at',
    }[new_status]
    setattr(req, status_time_field, timezone.now())
    req.save(update_fields=['status', status_time_field])

    if new_status == 'accepted':
        req.donation.status = 'accepted'
        req.donation.save()
    elif new_status == 'rejected':
        req.donation.status = 'posted'
        req.donation.save()
    elif new_status == 'completed':
        req.donation.status = 'completed'
        req.donation.save()

    Notification.objects.create(
        user=req.receiver,
        message=(
            f"Your request for '{req.donation.food_name}' was accepted. "
            f"Pickup is confirmed for {timezone.localtime(req.pickup_time):%d %b %Y, %H:%M}."
            if new_status == 'accepted' and req.pickup_time
            else f"Your request for '{req.donation.food_name}' was {new_status}."
        ),
        donation=req.donation
    )
    messages.success(request, f'Request marked as {new_status}.')
    return redirect('incoming_requests')

@login_required
def cancel_request(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk, receiver=request.user)

    if req.status != 'pending':
        messages.error(request, 'You can only cancel pending requests.')
        return redirect('my_requests')

    donation = req.donation
    req.delete()
    donation.status = 'posted'
    donation.save()
    messages.success(request, 'Request cancelled successfully.')
    return redirect('my_requests')

@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread = notes.filter(is_read=False)
    unread.update(is_read=True)
    return render(request, 'requests_app/notifications.html', {'notifications': notes})

@login_required
def rate_donation(request, pk):
    req = get_object_or_404(DonationRequest, pk=pk, receiver=request.user)

    if req.status != 'completed':
        messages.error(request, 'You can only rate completed donations.')
        return redirect('my_requests')

    if hasattr(req, 'rating'):
        messages.warning(request, 'You have already rated this donation.')
        return redirect('my_requests')

    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.donation_request = req
            rating.rated_by = request.user
            rating.rated_user = req.donation.donor
            rating.save()
            messages.success(request, 'Thank you for your feedback!')
            return redirect('my_requests')
    else:
        form = RatingForm()
    return render(request, 'requests_app/rate_donation.html', {'form': form, 'req': req})