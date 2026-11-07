from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from .models import User, VerificationRequest

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


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        'organization_name',
        'user',
        'organization_type',
        'status',
        'requested_at',
        'reviewed_at',
        'reviewed_by',
    )
    list_filter = ('status', 'organization_type', 'requested_at')
    search_fields = ('organization_name', 'user__username', 'user__email')
    readonly_fields = ('status', 'requested_at', 'reviewed_at', 'reviewed_by')
    actions = ('approve_requests', 'decline_requests')

    @admin.action(description='Approve selected verification requests')
    def approve_requests(self, request, queryset):
        reviewed = 0
        for verification_request in queryset.filter(status=VerificationRequest.STATUS_PENDING):
            verification_request.approve(request.user)
            reviewed += 1
        self.message_user(
            request,
            f'{reviewed} verification request(s) approved.',
            messages.SUCCESS,
        )

    @admin.action(description='Decline selected verification requests')
    def decline_requests(self, request, queryset):
        reviewed = 0
        for verification_request in queryset.filter(status=VerificationRequest.STATUS_PENDING):
            verification_request.decline(request.user)
            reviewed += 1
        self.message_user(
            request,
            f'{reviewed} verification request(s) declined.',
            messages.SUCCESS,
        )