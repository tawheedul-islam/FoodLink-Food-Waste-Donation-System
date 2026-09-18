from django.contrib import admin
from .models import FoodDonation

@admin.register(FoodDonation)
class FoodDonationAdmin(admin.ModelAdmin):
    list_display = ('food_name', 'donor', 'category', 'quantity', 'status', 'expiry_time', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('food_name', 'pickup_location', 'donor__username')
    ordering = ('-created_at',)