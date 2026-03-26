from django.contrib import admin
from .models import VolunteerProfile


@admin.register(VolunteerProfile)
class VolunteerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_latitude', 'last_longitude', 'updated_at')
    readonly_fields = ('updated_at',)
