from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from donations.models import FoodDonation
from .models import DonationRequest

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

    messages.success(request, f'Request marked as {new_status}.')
    return redirect('incoming_requests')