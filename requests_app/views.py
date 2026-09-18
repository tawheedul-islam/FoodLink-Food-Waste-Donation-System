from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from donations.models import FoodDonation
from .models import DonationRequest, Notification

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

    DonationRequest.objects.create(donation=donation, receiver=request.user)
    donation.status = 'requested'
    donation.save()

    Notification.objects.create(
        user=donation.donor,
        message=f"{request.user.username} requested your donation '{donation.food_name}'.",
        donation=donation
    )
    messages.success(request, 'Request submitted successfully!')
    return redirect('my_requests')

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
    req = get_object_or_404(DonationRequest, pk=pk, donation__donor=request.user)
    req.status = new_status
    req.save()

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
        message=f"Your request for '{req.donation.food_name}' was {new_status}.",
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