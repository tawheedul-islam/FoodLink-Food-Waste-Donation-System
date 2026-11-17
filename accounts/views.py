from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .forms import RegisterForm, ProfileEditForm, VerificationRequestForm
from .forms import OrganizationForm, OrganizationInviteForm
from .models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    User,
    VerificationRequest,
)
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
        my_requests = DonationRequest.objects.filter(
            Q(receiver=request.user)
            | Q(receiver_organization__memberships__user=request.user)
        ).distinct()
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


@login_required
def organization_list(request):
    if request.user.role not in {'donor', 'receiver'}:
        messages.error(request, 'Only donors and receivers can use organization workspaces.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = OrganizationForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(request, 'Organization workspace created.')
            return redirect('organizations')
    else:
        form = OrganizationForm(user=request.user)

    organizations = Organization.objects.filter(
        memberships__user=request.user,
    ).distinct()
    invitations = OrganizationInvitation.objects.filter(
        invited_user=request.user,
        status=OrganizationInvitation.STATUS_PENDING,
    ).select_related('organization', 'invited_by')
    return render(request, 'accounts/organizations.html', {
        'form': form,
        'organizations': organizations,
        'invitations': invitations,
    })


@login_required
def organization_detail(request, pk):
    organization = get_object_or_404(
        Organization.objects.filter(memberships__user=request.user),
        pk=pk,
    )
    is_owner = organization.is_owner(request.user)
    members = organization.memberships.select_related('user')
    invitations = organization.invitations.filter(
        status=OrganizationInvitation.STATUS_PENDING,
    ).select_related('invited_user') if is_owner else OrganizationInvitation.objects.none()
    invite_form = OrganizationInviteForm(
        organization=organization,
        invited_by=request.user,
    ) if is_owner else None
    donations = organization.donations.order_by('-created_at')
    organization_requests = organization.organization_requests.select_related(
        'donation',
        'receiver',
        'donation__donor',
    ).order_by('-request_date')
    return render(request, 'accounts/organization_detail.html', {
        'organization': organization,
        'is_owner': is_owner,
        'members': members,
        'invitations': invitations,
        'invite_form': invite_form,
        'donations': donations,
        'organization_requests': organization_requests,
    })


@login_required
def invite_organization_member(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    if request.method != 'POST':
        messages.error(request, 'Use the invite form to add organization members.')
        return redirect('organization_detail', pk=pk)
    if not organization.is_owner(request.user):
        messages.error(request, 'Only organization owners can invite members.')
        return redirect('organizations')

    form = OrganizationInviteForm(
        request.POST,
        organization=organization,
        invited_by=request.user,
    )
    if form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, 'Invitation sent. The user can accept it from Organizations.')
        return redirect('organization_detail', pk=pk)

    members = organization.memberships.select_related('user')
    invitations = organization.invitations.filter(
        status=OrganizationInvitation.STATUS_PENDING,
    ).select_related('invited_user')
    return render(request, 'accounts/organization_detail.html', {
        'organization': organization,
        'is_owner': True,
        'members': members,
        'invitations': invitations,
        'invite_form': form,
        'donations': organization.donations.order_by('-created_at'),
        'organization_requests': organization.organization_requests.select_related(
            'donation',
            'receiver',
            'donation__donor',
        ).order_by('-request_date'),
    })


@login_required
def respond_to_organization_invitation(request, pk, action):
    if request.method != 'POST' or action not in {'accept', 'decline'}:
        messages.error(request, 'Invalid invitation action.')
        return redirect('organizations')

    invitation = get_object_or_404(
        OrganizationInvitation.objects.select_related('organization'),
        pk=pk,
        invited_user=request.user,
        status=OrganizationInvitation.STATUS_PENDING,
    )
    if action == 'accept':
        if request.user.role != invitation.organization.role:
            messages.error(request, 'Your account role no longer matches this organization.')
            return redirect('organizations')
        with transaction.atomic():
            OrganizationMembership.objects.get_or_create(
                organization=invitation.organization,
                user=request.user,
                defaults={'role': OrganizationMembership.ROLE_MEMBER},
            )
            invitation.status = OrganizationInvitation.STATUS_ACCEPTED
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=['status', 'responded_at'])
        messages.success(request, f'You joined {invitation.organization.name}.')
    else:
        invitation.status = OrganizationInvitation.STATUS_DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])
        messages.success(request, 'Invitation declined.')
    return redirect('organizations')


@login_required
def remove_organization_member(request, pk, user_id):
    organization = get_object_or_404(Organization, pk=pk)
    if request.method != 'POST':
        messages.error(request, 'Use the member controls to update workspace membership.')
        return redirect('organization_detail', pk=pk)
    if not organization.is_owner(request.user):
        messages.error(request, 'Only organization owners can remove members.')
        return redirect('organization_detail', pk=pk)

    membership = get_object_or_404(
        OrganizationMembership.objects.select_related('user'),
        organization=organization,
        user_id=user_id,
        role=OrganizationMembership.ROLE_MEMBER,
    )
    membership.delete()
    messages.success(request, f'{membership.user.username} was removed from the workspace.')
    return redirect('organization_detail', pk=pk)