from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import FoodDonation
from .forms import FoodDonationForm

@login_required
def donation_list(request):
    if request.user.role == 'donor':
        donations = FoodDonation.objects.filter(donor=request.user).order_by('-created_at')
    else:
        donations = FoodDonation.objects.filter(status='posted').order_by('-created_at')

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
        form = FoodDonationForm(request.POST)
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
    return render(request, 'donations/donation_detail.html', {'donation': donation})