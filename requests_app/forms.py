from django import forms
from django.utils import timezone
from .models import Rating
from donations.models import FoodDonation


class PickupRequestForm(forms.Form):
    pickup_time = forms.DateTimeField(
        label='Preferred pickup time',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
    )

    def __init__(self, *args, donation, **kwargs):
        self.donation = donation
        super().__init__(*args, **kwargs)
        if donation.pickup_window_start:
            self.fields['pickup_time'].widget.attrs['min'] = timezone.localtime(
                donation.pickup_window_start
            ).strftime('%Y-%m-%dT%H:%M')
        if donation.pickup_window_end:
            self.fields['pickup_time'].widget.attrs['max'] = timezone.localtime(
                donation.pickup_window_end
            ).strftime('%Y-%m-%dT%H:%M')

    def clean_pickup_time(self):
        pickup_time = self.cleaned_data['pickup_time']
        donation = self.donation
        if pickup_time <= timezone.now():
            raise forms.ValidationError("Choose a pickup time in the future.")
        if pickup_time >= donation.expiry_time:
            raise forms.ValidationError("Pickup must be scheduled before the food expires.")
        if donation.pickup_window_start and pickup_time < donation.pickup_window_start:
            raise forms.ValidationError("Choose a time within the donor's pickup availability.")
        if donation.pickup_window_end and pickup_time > donation.pickup_window_end:
            raise forms.ValidationError("Choose a time within the donor's pickup availability.")
        return pickup_time

class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['score', 'comment']
        widgets = {
            'score': forms.Select(
                choices=[(5,'★★★★★ Excellent'),(4,'★★★★☆ Good'),(3,'★★★☆☆ Average'),(2,'★★☆☆☆ Poor'),(1,'★☆☆☆☆ Very Poor')],
                attrs={'class': 'form-select'}
            ),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional feedback about this donation...'}),
        }