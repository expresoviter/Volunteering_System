from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from apps.tasks.models import Task


@login_required
def profile(request):
    if not request.user.is_volunteer():
        return redirect('tasks:task_list')

    user = request.user
    active_task = Task.objects.filter(
        assigned_to=user,
        status=Task.Status.IN_PROGRESS,
    ).first()
    completed_tasks = Task.objects.filter(
        assigned_to=user,
        status=Task.Status.COMPLETED,
    ).order_by('-updated_at')

    context = {
        'active_task': active_task,
        'completed_tasks': completed_tasks,
        'completed_count': completed_tasks.count(),
    }
    return render(request, 'volunteers/profile.html', context)
