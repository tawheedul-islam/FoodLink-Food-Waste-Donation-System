from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm
from .models import User
from donations.models import FoodDonation
from requests_app.models import DonationRequest

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
    return render(request, 'accounts/dashboard.html')

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('dashboard')

    context = {
        'total_users': User.objects.count(),
        'total_donors': User.objects.filter(role='donor').count(),
        'total_receivers': User.objects.filter(role='receiver').count(),
        'total_donations': FoodDonation.objects.count(),
        'posted_donations': FoodDonation.objects.filter(status='posted').count(),
        'completed_donations': FoodDonation.objects.filter(status='completed').count(),
        'total_requests': DonationRequest.objects.count(),
        'pending_requests': DonationRequest.objects.filter(status='pending').count(),
    }
    return render(request, 'accounts/admin_dashboard.html', context)