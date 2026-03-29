import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_assigned_to_m2m(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    for task in Task.objects.filter(assigned_to__isnull=False):
        task.assigned_volunteers.add(task.assigned_to)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_task_is_archived'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='volunteers_needed',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='task',
            name='assigned_volunteers',
            field=models.ManyToManyField(
                blank=True,
                related_name='accepted_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrate_assigned_to_m2m, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='task',
            name='assigned_to',
        ),
    ]
