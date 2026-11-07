from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('donor', 'Donor'),
        ('receiver', 'Receiver'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='donor')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(
        default=False,
        help_text='Mark only after completing the verification review.',
    )
    verified_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    def average_rating(self):
        from requests_app.models import Rating
        ratings = Rating.objects.filter(rated_user=self)
        if ratings.exists():
            return round(sum(r.score for r in ratings) / ratings.count(), 1)
        return None


class VerificationRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DECLINED, 'Declined'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_requests',
    )
    organization_name = models.CharField(max_length=150)
    organization_type = models.CharField(max_length=100)
    organization_website = models.URLField(blank=True)
    organization_summary = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    review_note = models.CharField(max_length=500, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='verification_reviews',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('-requested_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(status='pending'),
                name='one_pending_verification_request_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.organization_name} — {self.get_status_display()}"

    def approve(self, reviewer):
        self._record_review(self.STATUS_APPROVED, reviewer)
        user = self.user
        if not user.is_verified:
            user.is_verified = True
            user.verified_at = self.reviewed_at
            user.save(update_fields=['is_verified', 'verified_at'])

    def decline(self, reviewer):
        self._record_review(self.STATUS_DECLINED, reviewer)

    def _record_review(self, status, reviewer):
        if self.status != self.STATUS_PENDING:
            raise ValueError('Only pending verification requests can be reviewed.')
        self.status = status
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])