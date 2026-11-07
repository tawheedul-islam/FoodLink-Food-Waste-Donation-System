from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm, ProfileEditForm, VerificationRequestForm
from .models import User, VerificationRequest
from donations.models import FoodDonation
from requests_app.models import DonationRequest
from requests_app.models import Rating


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

def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    context = {
        'donation_count': FoodDonation.objects.count(),
        'completed_count': FoodDonation.objects.filter(status='completed').count(),
        'user_count': User.objects.count(),
    }
    return render(request, 'accounts/home.html', context)

@login_required
def dashboard_view(request):
    context = {}
    if request.user.role == 'donor':
        donations = FoodDonation.objects.filter(donor=request.user)
        context['total_donations'] = donations.count()
        context['posted_count'] = donations.filter(status='posted').count()
        context['completed_count'] = donations.filter(status='completed').count()
        context['pending_requests_count'] = DonationRequest.objects.filter(
            donation__donor=request.user, status='pending'
        ).count()
        completed_requests = DonationRequest.objects.filter(status='completed')
        context['personal_completed_count'] = donations.filter(
            status='completed',
            requests__status='completed',
        ).distinct().count()
        context['completed_count'] = context['personal_completed_count']
        ratings = Rating.objects.filter(rated_user=request.user).order_by('-created_at')
        context['ratings'] = ratings
        context['avg_rating'] = request.user.average_rating()
    elif request.user.role == 'receiver':
        my_requests = DonationRequest.objects.filter(receiver=request.user)
        context['total_requests'] = my_requests.count()
        context['pending_count'] = my_requests.filter(status='pending').count()
        context['accepted_count'] = my_requests.filter(status='accepted').count()
        context['completed_count'] = my_requests.filter(status='completed').count()
        context['personal_completed_count'] = context['completed_count']

    if request.user.role in {'donor', 'receiver'}:
        context['latest_verification_request'] = VerificationRequest.objects.filter(
            user=request.user,
        ).first()
        completed_requests = DonationRequest.objects.filter(status='completed')
        context['community_completed_donations'] = (
            completed_requests.values('donation_id').distinct().count()
        )
        context['community_donors'] = (
            completed_requests.values('donation__donor_id').distinct().count()
        )
        context['community_receivers'] = (
            completed_requests.values('receiver_id').distinct().count()
        )

    return render(request, 'accounts/dashboard.html', context)

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

@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def verification_request_view(request):
    if request.user.role not in {'donor', 'receiver'}:
        messages.error(request, 'Only donors and receivers can request verification.')
        return redirect('dashboard')
    if request.user.is_verified:
        messages.info(request, 'Your account is already verified.')
        return redirect('dashboard')

    pending_request = VerificationRequest.objects.filter(
        user=request.user,
        status=VerificationRequest.STATUS_PENDING,
    ).first()
    if pending_request:
        messages.info(request, 'Your verification request is awaiting admin review.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = VerificationRequestForm(request.POST, user=request.user)
        if form.is_valid():
            verification_request = form.save(commit=False)
            verification_request.user = request.user
            verification_request.save()
            messages.success(request, 'Verification request submitted for admin review.')
            return redirect('dashboard')
    else:
        form = VerificationRequestForm(user=request.user)

    return render(request, 'accounts/verification_request.html', {'form': form})