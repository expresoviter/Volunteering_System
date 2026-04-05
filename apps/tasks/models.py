from django.db import models
from django.conf import settings


class Task(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    class Priority(models.IntegerChoices):
        LOW = 1, 'Low'
        MEDIUM = 2, 'Medium'
        HIGH = 3, 'High (Urgent)'

    title = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=500)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    priority = models.IntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    volunteers_needed = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
    )
    assigned_volunteers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='accepted_tasks',
    )
    required_skills = models.ManyToManyField(
        'volunteers.Skill',
        blank=True,
        related_name='tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title} — {self.get_status_display()}"

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def volunteers_count(self):
        return self.assigned_volunteers.count()

    @property
    def slots_available(self):
        return self.volunteers_count < self.volunteers_needed
