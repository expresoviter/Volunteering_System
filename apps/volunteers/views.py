from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from apps.tasks.models import Task
from .models import Skill, VolunteerProfile


@login_required
def profile(request):
    if not request.user.is_volunteer():
        return redirect('tasks:task_list')

    user = request.user
    active_task = Task.objects.filter(
        assigned_volunteers=user,
        status=Task.Status.IN_PROGRESS,
    ).first()
    completed_tasks = Task.objects.filter(
        assigned_volunteers=user,
        status=Task.Status.COMPLETED,
    ).order_by('-updated_at')

    profile_obj, _ = VolunteerProfile.objects.get_or_create(user=user)
    volunteer_skills = profile_obj.skills.order_by('category', 'name')

    context = {
        'active_task': active_task,
        'completed_tasks': completed_tasks,
        'completed_count': completed_tasks.count(),
        'volunteer_skills': volunteer_skills,
    }
    return render(request, 'volunteers/profile.html', context)


@login_required
def profile_edit(request):
    if not request.user.is_volunteer():
        return redirect('tasks:task_list')

    profile_obj, _ = VolunteerProfile.objects.get_or_create(user=request.user)

    skills_by_category = {}
    for skill in Skill.objects.order_by('category', 'name'):
        skills_by_category.setdefault(skill.get_category_display(), []).append(skill)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('skills')
        profile_obj.skills.set(Skill.objects.filter(id__in=selected_ids))
        messages.success(request, "Your skills have been updated.")
        return redirect('volunteers:profile')

    selected_skill_ids = set(str(i) for i in profile_obj.skills.values_list('id', flat=True))

    return render(request, 'volunteers/profile_edit.html', {
        'skills_by_category': skills_by_category,
        'selected_skill_ids': selected_skill_ids,
    })
