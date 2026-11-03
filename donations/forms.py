from django import forms
from django.utils import timezone
from .models import FoodDonation

class FoodDonationForm(forms.ModelForm):
    class Meta:
        model = FoodDonation
        fields = ['food_name', 'category', 'quantity', 'description',
                  'allergen_info', 'storage_instructions', 'packaging_info',
                  'preparation_time', 'expiry_time', 'pickup_location',
                  'pickup_latitude', 'pickup_longitude',
                  'pickup_window_start', 'pickup_window_end', 'image']
        widgets = {
            'food_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Chicken Biryani'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10 kg or 20 plates'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any extra details about the food...'}),
            'allergen_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'List known allergens, or say if this information is unknown',
            }),
            'storage_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'e.g. Keep refrigerated; reheat thoroughly before serving',
            }),
            'packaging_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'e.g. Sealed containers; contains 4 separate portions',
            }),
            'preparation_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expiry_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'pickup_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Rangamati Sadar'}),
            'pickup_latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g. 22.3569',
            }),
            'pickup_longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g. 91.7832',
            }),
            'pickup_window_start': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'pickup_window_end': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['pickup_window_start'].required = True
            self.fields['pickup_window_end'].required = True

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
        pickup_start = cleaned_data.get('pickup_window_start')
        pickup_end = cleaned_data.get('pickup_window_end')
        latitude = cleaned_data.get('pickup_latitude')
        longitude = cleaned_data.get('pickup_longitude')

        if prep_time and expiry_time and prep_time >= expiry_time:
            raise forms.ValidationError("Expiry time must be after preparation time.")
        if bool(pickup_start) != bool(pickup_end):
            raise forms.ValidationError("Provide both pickup window start and end times.")
        if pickup_start and pickup_end:
            if pickup_start <= timezone.now():
                self.add_error('pickup_window_start', "Pickup availability must start in the future.")
            if pickup_start >= pickup_end:
                self.add_error('pickup_window_end', "Pickup window end must be after its start.")
            if expiry_time and pickup_end > expiry_time:
                self.add_error('pickup_window_end', "Pickup availability must end before the food expires.")
        if (latitude is None) != (longitude is None):
            self.add_error('pickup_latitude', "Provide both pickup coordinates or leave both blank.")
            self.add_error('pickup_longitude', "Provide both pickup coordinates or leave both blank.")

        return cleaned_data