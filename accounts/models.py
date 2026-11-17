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


class Organization(models.Model):
    ROLE_CHOICES = (
        ('donor', 'Donor organization'),
        ('receiver', 'Receiver organization'),
    )

    name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    description = models.TextField(blank=True, max_length=1000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organizations_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='OrganizationMembership',
        related_name='organizations',
    )

    class Meta:
        ordering = ('name', 'pk')

    def __str__(self):
        return self.name

    def has_member(self, user):
        return self.memberships.filter(user=user).exists()

    def is_owner(self, user):
        return self.memberships.filter(user=user, role='owner').exists()


class OrganizationMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = (
        (ROLE_OWNER, 'Owner'),
        (ROLE_MEMBER, 'Member'),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('joined_at', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'user'],
                name='unique_organization_membership',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.organization.name} ({self.role})"


class OrganizationInvitation(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_DECLINED, 'Declined'),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_invitations',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organization_invitations_sent',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'invited_user'],
                condition=Q(status='pending'),
                name='one_pending_organization_invitation',
            ),
        ]

    def __str__(self):
        return f"{self.organization.name} → {self.invited_user.username} ({self.status})"