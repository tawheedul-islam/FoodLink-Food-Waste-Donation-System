from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, VerificationRequest

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