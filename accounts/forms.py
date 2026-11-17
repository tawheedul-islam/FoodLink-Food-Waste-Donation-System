from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    User,
    VerificationRequest,
)

class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[('donor', 'Donor'), ('receiver', 'Receiver')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone_number = forms.CharField(
        max_length=15, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 01712345678'})
    )
    address = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your address'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'phone_number', 'address', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and (not phone.isdigit() or len(phone) < 10):
            raise forms.ValidationError("Enter a valid phone number (at least 10 digits).")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        
        
class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and (not phone.isdigit() or len(phone) < 10):
            raise forms.ValidationError("Enter a valid phone number (at least 10 digits).")
        return phone


class VerificationRequestForm(forms.ModelForm):
    class Meta:
        model = VerificationRequest
        fields = [
            'organization_name',
            'organization_type',
            'organization_website',
            'organization_summary',
        ]
        widgets = {
            'organization_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Organization or community group name',
            }),
            'organization_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Community kitchen, registered NGO, local shelter',
            }),
            'organization_website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.org (optional)',
            }),
            'organization_summary': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Briefly describe your organization and how it participates in food donation or distribution.',
            }),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_organization_name(self):
        value = self.cleaned_data['organization_name'].strip()
        if len(value) < 2:
            raise forms.ValidationError('Enter your organization name.')
        return value

    def clean_organization_type(self):
        return self.cleaned_data['organization_type'].strip()

    def clean_organization_summary(self):
        return self.cleaned_data['organization_summary'].strip()

    def save(self, commit=True):
        verification_request = super().save(commit=False)
        verification_request.user = self.user
        if commit:
            verification_request.save()
        return verification_request


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'role', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Organization or team name',
            }),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'A short description of your team (optional)',
            }),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user.role in {'donor', 'receiver'}:
            self.fields['role'].choices = [
                (user.role, dict(Organization.ROLE_CHOICES)[user.role]),
            ]
        else:
            self.fields['role'].choices = []

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Enter an organization name.')
        return name

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('role') != self.user.role:
            self.add_error('role', 'Your account role must match the organization workspace type.')
        return cleaned_data

    def save(self, commit=True):
        organization = super().save(commit=False)
        organization.created_by = self.user
        if commit:
            organization.save()
            OrganizationMembership.objects.create(
                organization=organization,
                user=self.user,
                role=OrganizationMembership.ROLE_OWNER,
            )
        return organization


class OrganizationInviteForm(forms.Form):
    username = forms.CharField(
        label='Member username',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter an existing FoodLink username',
        }),
    )

    def __init__(self, *args, organization, invited_by, **kwargs):
        self.organization = organization
        self.invited_by = invited_by
        self.invited_user = None
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        try:
            invited_user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise forms.ValidationError('No FoodLink account was found with that username.')

        if invited_user == self.invited_by:
            raise forms.ValidationError('You are already an owner of this workspace.')
        if invited_user.role != self.organization.role:
            raise forms.ValidationError('The invited user must have the same role as the organization.')
        if OrganizationMembership.objects.filter(
            organization=self.organization,
            user=invited_user,
        ).exists():
            raise forms.ValidationError('This user is already a workspace member.')
        if OrganizationInvitation.objects.filter(
            organization=self.organization,
            invited_user=invited_user,
            status=OrganizationInvitation.STATUS_PENDING,
        ).exists():
            raise forms.ValidationError('This user already has a pending invitation.')

        self.invited_user = invited_user
        return username

    def save(self):
        if not self.is_valid():
            raise ValueError('Cannot create an invitation from an invalid form.')
        return OrganizationInvitation.objects.create(
            organization=self.organization,
            invited_user=self.invited_user,
            invited_by=self.invited_by,
        )