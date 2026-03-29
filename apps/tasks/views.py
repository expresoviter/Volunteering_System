import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TaskForm
from .models import Task
from .services.geocoding import geocode_address
from .services.matching import get_recommended_tasks_for_volunteer, VolunteerInput
from apps.volunteers.models import VolunteerProfile

logger = logging.getLogger(__name__)


@login_required
def task_list(request):
    """
    Main task list / map view.
    For volunteers: shows nearby tasks with Hungarian-algorithm recommendations.
    For coordinators: shows all tasks.
    """
    user = request.user
    volunteer_lat = request.session.get('volunteer_lat')
    volunteer_lon = request.session.get('volunteer_lon')

    if user.is_coordinator():
        tasks = Task.objects.filter(is_archived=False).prefetch_related('assigned_volunteers', 'created_by')
        recommended_ids = set()
    else:
        # Volunteer view: filter by radius if location is known
        if volunteer_lat and volunteer_lon:
            from django.conf import settings
            from geopy.distance import geodesic
            radius_km = settings.TASK_RADIUS_KM
            open_tasks = Task.objects.filter(status=Task.Status.OPEN, is_archived=False)
            nearby_tasks = []
            for task in open_tasks:
                if task.has_coordinates:
                    distance = geodesic(
                        (volunteer_lat, volunteer_lon),
                        (task.latitude, task.longitude),
                    ).km
                    if distance <= radius_km:
                        nearby_tasks.append(task)
            tasks = Task.objects.filter(
                id__in=[t.id for t in nearby_tasks]
            ).prefetch_related('assigned_volunteers', 'created_by')

            recommended_ids = get_recommended_tasks_for_volunteer(
                volunteer_id=user.id,
                volunteer_lat=float(volunteer_lat),
                volunteer_lon=float(volunteer_lon),
                open_tasks=nearby_tasks,
            )
        else:
            tasks = Task.objects.filter(
                status=Task.Status.OPEN, is_archived=False
            ).prefetch_related('assigned_volunteers', 'created_by')
            recommended_ids = set()

    # Build GeoJSON for map markers
    features = []
    for task in tasks:
        if task.has_coordinates:
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [task.longitude, task.latitude]},
                'properties': {
                    'id': task.id,
                    'title': task.title,
                    'status': task.status,
                    'priority': task.priority,
                    'recommended': task.id in recommended_ids,
                    'volunteers_count': task.volunteers_count,
                    'volunteers_needed': task.volunteers_needed,
                    'url': f'/tasks/{task.id}/',
                },
            })
    geojson = json.dumps({'type': 'FeatureCollection', 'features': features})

    context = {
        'tasks': tasks,
        'recommended_ids': recommended_ids,
        'geojson': geojson,
        'volunteer_lat': volunteer_lat,
        'volunteer_lon': volunteer_lon,
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    assigned_volunteers = task.assigned_volunteers.all()
    user_already_accepted = request.user in assigned_volunteers
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'assigned_volunteers': assigned_volunteers,
        'user_already_accepted': user_already_accepted,
    })


@login_required
def task_create(request):
    if not request.user.is_coordinator():
        messages.error(request, "Only coordinators can create tasks.")
        return redirect('tasks:task_list')
    if not request.user.can_work():
        messages.warning(request, "Your account is pending verification.")
        return redirect('accounts:pending_verification')

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            lat, lon = geocode_address(task.address)
            task.latitude = lat
            task.longitude = lon
            task.save()
            if lat is None:
                messages.warning(
                    request,
                    f"Task saved but address '{task.address}' could not be geocoded. "
                    "The task will not appear on the map until a valid address is provided."
                )
            else:
                messages.success(request, f"Task '{task.title}' created successfully.")
            return redirect('tasks:task_detail', pk=task.pk)
    else:
        form = TaskForm()

    return render(request, 'tasks/task_form.html', {'form': form, 'action': 'Create'})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not request.user.is_coordinator():
        messages.error(request, "Only coordinators can edit tasks.")
        return redirect('tasks:task_detail', pk=pk)
    if not request.user.can_work():
        messages.warning(request, "Your account is pending verification.")
        return redirect('accounts:pending_verification')

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            lat, lon = geocode_address(task.address)
            task.latitude = lat
            task.longitude = lon
            task.save()
            messages.success(request, "Task updated.")
            return redirect('tasks:task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task)

    return render(request, 'tasks/task_form.html', {'form': form, 'action': 'Edit', 'task': task})


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not request.user.is_coordinator():
        messages.error(request, "Only coordinators can delete tasks.")
        return redirect('tasks:task_detail', pk=pk)
    if not request.user.can_work():
        messages.warning(request, "Your account is pending verification.")
        return redirect('accounts:pending_verification')
    if task.assigned_volunteers.exists() or task.status == Task.Status.COMPLETED:
        task.is_archived = True
        task.save(update_fields=['is_archived'])
        messages.success(request, f"Task '{task.title}' archived.")
    else:
        task.delete()
        messages.success(request, f"Task '{task.title}' deleted.")
    return redirect('tasks:task_list')


@login_required
def task_archive_list(request):
    if not request.user.is_coordinator():
        messages.error(request, "Only coordinators can view the archive.")
        return redirect('tasks:task_list')
    if not request.user.can_work():
        messages.warning(request, "Your account is pending verification.")
        return redirect('accounts:pending_verification')
    archived_tasks = Task.objects.filter(is_archived=True).prefetch_related('assigned_volunteers', 'created_by')
    return render(request, 'tasks/task_archive.html', {'archived_tasks': archived_tasks})


@login_required
@require_POST
def task_accept(request, pk):
    """Volunteer accepts an open task — added to assigned_volunteers."""
    task = get_object_or_404(Task, pk=pk, status=Task.Status.OPEN)
    if not request.user.is_volunteer():
        messages.error(request, "Only volunteers can accept tasks.")
        return redirect('tasks:task_detail', pk=pk)
    if request.user in task.assigned_volunteers.all():
        messages.warning(request, "You have already accepted this task.")
        return redirect('tasks:task_detail', pk=pk)
    if not task.slots_available:
        messages.error(request, "This task has no available slots.")
        return redirect('tasks:task_detail', pk=pk)

    task.assigned_volunteers.add(request.user)
    if task.assigned_volunteers.count() >= task.volunteers_needed:
        task.status = Task.Status.IN_PROGRESS
        task.save(update_fields=['status', 'updated_at'])

    messages.success(request, f"You accepted task '{task.title}'.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_complete(request, pk):
    """Mark a task as Completed. Only coordinators can do this."""
    task = get_object_or_404(Task, pk=pk)
    user = request.user
    if not user.is_coordinator():
        messages.error(request, "Only coordinators can mark tasks as completed.")
        return redirect('tasks:task_detail', pk=pk)
    if not user.can_work():
        messages.warning(request, "Your account is pending verification.")
        return redirect('accounts:pending_verification')
    if task.status == Task.Status.COMPLETED:
        messages.warning(request, "Task is already completed.")
        return redirect('tasks:task_detail', pk=pk)
    task.status = Task.Status.COMPLETED
    task.save()
    messages.success(request, f"Task '{task.title}' marked as Completed.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def update_location(request):
    """API endpoint: volunteer POSTs their current GPS coords → stored in session."""
    try:
        data = json.loads(request.body)
        lat = float(data['latitude'])
        lon = float(data['longitude'])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    request.session['volunteer_lat'] = lat
    request.session['volunteer_lon'] = lon

    if request.user.is_volunteer():
        profile, _ = VolunteerProfile.objects.get_or_create(user=request.user)
        profile.last_latitude = lat
        profile.last_longitude = lon
        profile.save(update_fields=['last_latitude', 'last_longitude', 'updated_at'])

    return JsonResponse({'status': 'ok', 'latitude': lat, 'longitude': lon})


@login_required
def tasks_geojson(request):
    """API endpoint returning all map-visible tasks as GeoJSON."""
    tasks = Task.objects.filter(is_archived=False).exclude(latitude=None).prefetch_related('assigned_volunteers', 'created_by')
    features = []
    for task in tasks:
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [task.longitude, task.latitude]},
            'properties': {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority,
                'volunteers_count': task.volunteers_count,
                'volunteers_needed': task.volunteers_needed,
                'url': f'/tasks/{task.id}/',
            },
        })
    return JsonResponse({'type': 'FeatureCollection', 'features': features})
