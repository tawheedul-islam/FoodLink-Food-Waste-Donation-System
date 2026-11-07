from django.contrib import admin
from django.utils import timezone
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_verified', 'phone_number', 'is_active', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('verified_at',)

    def save_model(self, request, obj, form, change):
        was_verified = form.initial.get('is_verified', False) if change else False
        if obj.is_verified and not was_verified:
            obj.verified_at = timezone.now()
        elif not obj.is_verified:
            obj.verified_at = None
        super().save_model(request, obj, form, change)