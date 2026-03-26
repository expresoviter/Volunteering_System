from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        VOLUNTEER = 'volunteer', 'Volunteer'
        COORDINATOR = 'coordinator', 'Coordinator'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VOLUNTEER,
    )

    def is_volunteer(self):
        return self.role == self.Role.VOLUNTEER

    def is_coordinator(self):
        return self.role == self.Role.COORDINATOR

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
