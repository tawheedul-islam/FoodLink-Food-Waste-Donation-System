from django.contrib import admin
from .models import DonationRequest, Notification

@admin.register(DonationRequest)
class DonationRequestAdmin(admin.ModelAdmin):
    list_display = ('donation', 'receiver', 'status', 'request_date')
    list_filter = ('status', 'request_date')
    search_fields = ('donation__food_name', 'receiver__username')
    ordering = ('-request_date',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')