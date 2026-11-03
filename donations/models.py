from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

class FoodDonation(models.Model):
    CATEGORY_CHOICES = (
        ('cooked', 'Cooked Food'),
        ('raw', 'Raw Food'),
        ('bakery', 'Bakery'),
        ('packaged', 'Packaged Food'),
        ('other', 'Other'),
    )
    STATUS_CHOICES = (
        ('posted', 'Posted'),
        ('requested', 'Requested'),
        ('accepted', 'Accepted'),
        ('collected', 'Collected'),
        ('completed', 'Completed'),
    )

    donor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donations')
    food_name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    allergen_info = models.TextField(blank=True)
    storage_instructions = models.TextField(blank=True)
    packaging_info = models.TextField(blank=True)
    preparation_time = models.DateTimeField(blank=True, null=True)
    expiry_time = models.DateTimeField()
    pickup_location = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    pickup_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    pickup_window_start = models.DateTimeField(blank=True, null=True)
    pickup_window_end = models.DateTimeField(blank=True, null=True)
    image = models.ImageField(upload_to='donation_images/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='posted')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.food_name} ({self.status})"