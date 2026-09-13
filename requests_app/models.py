from django.db import models
from django.conf import settings
from donations.models import FoodDonation

class DonationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )

    donation = models.ForeignKey(FoodDonation, on_delete=models.CASCADE, related_name='requests')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.receiver.username} → {self.donation.food_name} ({self.status})"