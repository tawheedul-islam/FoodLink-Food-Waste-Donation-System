from django import forms
from .models import FoodDonation

class FoodDonationForm(forms.ModelForm):
    class Meta:
        model = FoodDonation
        fields = ['food_name', 'category', 'quantity', 'description',
                  'preparation_time', 'expiry_time', 'pickup_location', 'image']
        widgets = {
            'food_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'preparation_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expiry_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'pickup_location': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }