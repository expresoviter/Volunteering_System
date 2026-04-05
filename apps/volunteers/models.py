from django.db import models
from django.conf import settings


class Skill(models.Model):
    CATEGORIES = [
        ('medical',   'Medical'),
        ('transport', 'Transport'),
        ('physical',  'Physical'),
        ('practical', 'Practical'),
        ('technical', 'Technical'),
        ('social',    'Social'),
        ('language',  'Language'),
    ]
    name     = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORIES)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class VolunteerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='volunteer_profile',
    )
    last_latitude  = models.FloatField(null=True, blank=True)
    last_longitude = models.FloatField(null=True, blank=True)
    skills         = models.ManyToManyField(Skill, blank=True, related_name='volunteers')
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def has_location(self):
        return self.last_latitude is not None and self.last_longitude is not None

    def completed_tasks_count(self):
        from apps.tasks.models import Task
        return Task.objects.filter(
            assigned_volunteers=self.user,
            status=Task.Status.COMPLETED,
        ).count()
