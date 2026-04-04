from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_verified = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='founded_organizations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # When an org is first verified, auto-verify all its coordinator members
        if self.pk:
            try:
                old = Organization.objects.get(pk=self.pk)
                if not old.is_verified and self.is_verified:
                    super().save(*args, **kwargs)
                    self.members.filter(role='coordinator').update(is_verified=True)
                    return
            except Organization.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class User(AbstractUser):
    class Role(models.TextChoices):
        VOLUNTEER = 'volunteer', 'Volunteer'
        COORDINATOR = 'coordinator', 'Coordinator'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VOLUNTEER,
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='members',
    )
    is_verified = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def is_volunteer(self):
        return self.role == self.Role.VOLUNTEER

    def is_coordinator(self):
        return self.role == self.Role.COORDINATOR

    def can_work(self):
        """Returns True if the user has full platform access."""
        return self.is_volunteer() or self.is_verified or self.is_superuser

    def can_manage_task(self, task):
        """Returns True if this coordinator may edit/delete the given task."""
        if not self.is_coordinator():
            return False
        if self.organization and self.organization.is_verified:
            return (
                task.created_by is not None
                and task.created_by.organization_id == self.organization_id
            )
        return task.created_by_id == self.pk

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
