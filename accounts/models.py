from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('donor', 'Donor'),
        ('receiver', 'Receiver'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='donor')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    def average_rating(self):
        from requests_app.models import Rating
        ratings = Rating.objects.filter(rated_user=self)
        if ratings.exists():
            return round(sum(r.score for r in ratings) / ratings.count(), 1)
        return None