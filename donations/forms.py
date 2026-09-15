from django import forms
from django.utils import timezone
from .models import FoodDonation

class FoodDonationForm(forms.ModelForm):
    class Meta:
        model = FoodDonation
        fields = ['food_name', 'category', 'quantity', 'description',
                  'preparation_time', 'expiry_time', 'pickup_location', 'image']
        widgets = {
            'food_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Chicken Biryani'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10 kg or 20 plates'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any extra details about the food...'}),
            'preparation_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expiry_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'pickup_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Rangamati Sadar'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_food_name(self):
        food_name = self.cleaned_data.get('food_name', '').strip()
        if len(food_name) < 2:
            raise forms.ValidationError("Food name must be at least 2 characters.")
        return food_name

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity', '').strip()
        if not quantity:
            raise forms.ValidationError("Please specify the quantity.")
        return quantity

    def clean_expiry_time(self):
        expiry_time = self.cleaned_data.get('expiry_time')
        if expiry_time and expiry_time <= timezone.now():
            raise forms.ValidationError("Expiry time must be in the future.")
        return expiry_time

    def clean(self):
        cleaned_data = super().clean()
        prep_time = cleaned_data.get('preparation_time')
        expiry_time = cleaned_data.get('expiry_time')

        if prep_time and expiry_time and prep_time >= expiry_time:
            raise forms.ValidationError("Expiry time must be after preparation time.")

        return cleaned_data