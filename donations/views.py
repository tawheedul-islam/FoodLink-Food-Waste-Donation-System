from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import FoodDonation
from .forms import FoodDonationForm
from requests_app.models import DonationRequest
from django.core.paginator import Paginator
from django.utils import timezone


@login_required
def donation_list(request):
    if request.user.role == 'donor':
        donations = FoodDonation.objects.filter(donor=request.user).order_by('-created_at')
    else:
       donations = FoodDonation.objects.filter(status='posted', expiry_time__gt=timezone.now()).order_by('-created_at')

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
        
    paginator = Paginator(donations, 6)  # 6 per page
    page_number = request.GET.get('page')
    donations = paginator.get_page(page_number)

    context = {
        'donations': donations,
        'category_choices': FoodDonation.CATEGORY_CHOICES,
        'selected_category': category,
        'query': query or '',
        'location': location or '',
    }
    return render(request, 'donations/donation_list.html', context)

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
    donation = get_object_or_404(FoodDonation, pk=pk)
    donation_requests = None
    if donation.donor == request.user:
        donation_requests = DonationRequest.objects.filter(donation=donation).order_by('-request_date')
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