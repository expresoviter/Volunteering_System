import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from geopy.distance import geodesic

from .forms import TaskForm
from .models import Task
from .services.geocoding import geocode_address_full

_ALLOWED_COUNTRY_CODES = {'ua', 'se', 'no'}
_COUNTRY_CODE_NAMES = {'ua': 'Ukraine', 'se': 'Sweden', 'no': 'Norway'}
from .services.matching import get_recommended_tasks_for_volunteer, VolunteerInput
from apps.accounts.models import Organization
from apps.volunteers.models import Skill, VolunteerProfile

logger = logging.getLogger(__name__)


def _skills_context(request, task):
    """Повертає skills_by_category та selected_skill_ids для форми завдання."""
    skills_by_category = {}
    for skill in Skill.objects.order_by('category', 'name'):
        skills_by_category.setdefault(skill.get_category_display(), []).append(skill)

    if request.method == 'POST':
        selected_skill_ids = set(request.POST.getlist('required_skills'))
    elif task is not None:
        selected_skill_ids = set(str(i) for i in task.required_skills.values_list('id', flat=True))
    else:
        selected_skill_ids = set()

    return {'skills_by_category': skills_by_category, 'selected_skill_ids': selected_skill_ids}


def _build_org_filter(selected_orgs, user):
    """Повертає Q-об'єкт для вибраних значень фільтра організацій або None, якщо фільтр не задано."""
    if not selected_orgs:
        return None
    q = Q()
    has_condition = False
    if 'mine' in selected_orgs and user.is_coordinator():
        q |= Q(created_by=user)
        has_condition = True
    if 'independent' in selected_orgs:
        q |= Q(created_by__isnull=True) | Q(created_by__organization__isnull=True)
        has_condition = True
    for val in selected_orgs:
        if val.isdigit():
            q |= Q(created_by__organization_id=int(val))
            has_condition = True
    return q if has_condition else None


def _apply_geocoding(form, task, post):
    """Геокодує адресу завдання, встановлює координати і перевіряє країну.
    Повертає True, якщо адреса дійсна; False і додає помилку форми — інакше."""
    try:
        lat = float(post['_coord_lat'])
        lon = float(post['_coord_lon'])
        geo = geocode_address_full(task.address)
        task.latitude  = lat
        task.longitude = lon
    except (KeyError, ValueError):
        geo = geocode_address_full(task.address)
        task.latitude  = geo['lat']
        task.longitude = geo['lon']

    country_code = (geo.get('country_code') or '').lower()
    if country_code not in _ALLOWED_COUNTRY_CODES:
        form.add_error(
            'address',
            "Завдання можна створювати лише в Україні, Швеції або Норвегії. "
            "Введіть адресу в одній з цих країн."
        )
        return False
    return True


def _revert_to_open_if_empty(task):
    """Повертає статус завдання до OPEN, якщо не залишилось призначених волонтерів."""
    if task.assigned_volunteers.count() == 0:
        task.status = Task.Status.OPEN
        task.save(update_fields=['status', 'updated_at'])


def _get_selected_orgs(request, user):
    """Повертає значення обраного фільтру за організаціями."""
    if 'filter_applied' in request.GET:
        return request.GET.getlist('org')
    if user.is_coordinator():
        if user.organization and user.organization.is_verified:
            return [str(user.organization_id)]
        return ['mine']
    return []


def _get_nearby_tasks_with_recommendations(request, user, open_tasks_base, org_q, prefetch, volunteer_lat, volunteer_lon):
    """Повертає завдання, рекомендації та радіуси для волонтера із вказаною локацією."""
    try:
        radius_km = max(1.0, min(100.0, float(request.GET.get('radius', settings.TASK_RADIUS_KM))))
    except (ValueError, TypeError):
        radius_km = settings.TASK_RADIUS_KM

    open_tasks_qs = open_tasks_base if org_q is None else open_tasks_base.filter(org_q)
    nearby_tasks = [
        task for task in open_tasks_qs
        if task.has_coordinates
        and geodesic((volunteer_lat, volunteer_lon), (task.latitude, task.longitude)).km <= radius_km
    ]

    tasks = Task.objects.filter(id__in=[t.id for t in nearby_tasks]).prefetch_related(*prefetch)

    try:
        volunteer_skill_ids = frozenset(user.volunteer_profile.skills.values_list('id', flat=True))
    except Exception:
        volunteer_skill_ids = frozenset()

    ranked_ids = get_recommended_tasks_for_volunteer(
        volunteer_id=user.id,
        volunteer_lat=float(volunteer_lat),
        volunteer_lon=float(volunteer_lon),
        open_tasks=nearby_tasks,
        volunteer_skill_ids=volunteer_skill_ids,
    )
    recommended_ids = {tid: rank for rank, tid in enumerate(ranked_ids[:3], start=1)}
    rank_position = {tid: pos for pos, tid in enumerate(ranked_ids)}
    tasks = sorted(tasks, key=lambda t: rank_position.get(t.id, len(ranked_ids)))
    return tasks, recommended_ids, radius_km


def _get_volunteer_tasks(request, user, org_q, prefetch, volunteer_lat, volunteer_lon):
    open_tasks_base = Task.objects.annotate(
        accepted_count=Count('assigned_volunteers')
    ).filter(
        status__in=[Task.Status.OPEN, Task.Status.IN_PROGRESS],
        is_archived=False,
        accepted_count__lt=F('volunteers_needed'),
    )

    if volunteer_lat and volunteer_lon:
        return _get_nearby_tasks_with_recommendations(
            request, user, open_tasks_base, org_q, prefetch, volunteer_lat, volunteer_lon
        )

    base_qs = open_tasks_base if org_q is None else open_tasks_base.filter(org_q)
    return base_qs.prefetch_related(*prefetch), {}, float(settings.TASK_RADIUS_KM)


def _build_task_geojson(tasks, recommended_ids):
    """Серіалізує завдання з координатами в GeoJSON FeatureCollection."""
    features = [
        {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [task.longitude, task.latitude]},
            'properties': {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority,
                'recommendation_rank': recommended_ids.get(task.id, 0),
                'volunteers_count': task.volunteers_count,
                'volunteers_needed': task.volunteers_needed,
                'url': f'/tasks/{task.id}/',
            },
        }
        for task in tasks
        if task.has_coordinates
    ]
    return json.dumps({'type': 'FeatureCollection', 'features': features})


@login_required
def task_list(request):
    """
    Головний список завдань / вигляд на карті.
    Для волонтерів: показує найближчі завдання з рекомендаціями угорського алгоритму.
    Для координаторів: показує всі завдання (за замовчуванням відфільтровані за організацією).
    """
    user = request.user
    volunteer_lat = request.session.get('volunteer_lat')
    volunteer_lon = request.session.get('volunteer_lon')
    prefetch = ['assigned_volunteers', 'created_by__organization', 'required_skills']

    selected_orgs = _get_selected_orgs(request, user)
    org_q = _build_org_filter(selected_orgs, user)

    if user.is_coordinator() or user.is_superuser:
        base_qs = Task.objects.filter(is_archived=False)
        if org_q is not None:
            base_qs = base_qs.filter(org_q)
        tasks = base_qs.prefetch_related(*prefetch)
        recommended_ids = {}
        radius_km = float(settings.TASK_RADIUS_KM)
    else:
        tasks, recommended_ids, radius_km = _get_volunteer_tasks(
            request, user, org_q, prefetch, volunteer_lat, volunteer_lon
        )

    for task in tasks:
        task.recommendation_rank = recommended_ids.get(task.id, 0)

    context = {
        'tasks': tasks,
        'recommended_ids': recommended_ids,
        'geojson': _build_task_geojson(tasks, recommended_ids),
        'volunteer_lat': volunteer_lat,
        'volunteer_lon': volunteer_lon,
        'location_source': request.session.get('location_source', 'gps'),
        'verified_orgs': Organization.objects.filter(is_verified=True),
        'selected_orgs': selected_orgs,
        'radius_km': radius_km,
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    assigned_volunteers = task.assigned_volunteers.all()
    user_already_accepted = request.user in assigned_volunteers
    can_manage = request.user.can_manage_task(task)
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'assigned_volunteers': assigned_volunteers,
        'user_already_accepted': user_already_accepted,
        'can_manage': can_manage,
    })


@login_required
def task_create(request):
    if not (request.user.is_coordinator() or request.user.is_superuser):
        messages.error(request, "Лише координатори можуть створювати завдання.")
        return redirect('tasks:task_list')
    if not request.user.can_work():
        messages.warning(request, "Ваш акаунт очікує верифікації.")
        return redirect('accounts:pending_verification')

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if _apply_geocoding(form, task, request.POST):
                task.save()
                task.required_skills.set(
                    Skill.objects.filter(id__in=request.POST.getlist('required_skills'))
                )
                if task.latitude is None:
                    messages.warning(
                        request,
                        f"Завдання збережено, але адресу '{task.address}' не вдалося геокодувати. "
                        "Завдання не з'явиться на карті, доки не буде вказана дійсна адреса."
                    )
                else:
                    messages.success(request, f"Завдання '{task.title}' успішно створено.")
                return redirect('tasks:task_detail', pk=task.pk)
    else:
        form = TaskForm()

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'action': 'Створити',
        **_skills_context(request, None),
    })


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_coordinator() or request.user.is_superuser):
        messages.error(request, "Лише координатори можуть редагувати завдання.")
        return redirect('tasks:task_detail', pk=pk)
    if not request.user.can_work():
        messages.warning(request, "Ваш акаунт очікує верифікації.")
        return redirect('accounts:pending_verification')
    if not request.user.can_manage_task(task):
        messages.error(request, "Ви можете редагувати лише завдання, створені вами або вашою організацією.")
        return redirect('tasks:task_detail', pk=pk)
    if task.status != Task.Status.OPEN or task.is_archived:
        messages.error(request, "Можна редагувати лише відкриті завдання.")
        return redirect('tasks:task_detail', pk=pk)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            if _apply_geocoding(form, task, request.POST):
                task.save()
                task.required_skills.set(
                    Skill.objects.filter(id__in=request.POST.getlist('required_skills'))
                )
                messages.success(request, "Завдання оновлено.")
                return redirect('tasks:task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task)

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'action': 'Редагувати',
        'task': task,
        **_skills_context(request, task),
    })


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_coordinator() or request.user.is_superuser):
        messages.error(request, "Лише координатори можуть видаляти завдання.")
        return redirect('tasks:task_detail', pk=pk)
    if not request.user.can_work():
        messages.warning(request, "Ваш акаунт очікує верифікації.")
        return redirect('accounts:pending_verification')
    if not request.user.can_manage_task(task):
        messages.error(request, "Ви можете видаляти лише завдання, створені вами або вашою організацією.")
        return redirect('tasks:task_detail', pk=pk)
    if task.assigned_volunteers.exists() or task.status == Task.Status.COMPLETED:
        task.is_archived = True
        if task.status == Task.Status.IN_PROGRESS:
            task.status = Task.Status.COMPLETED
        task.save(update_fields=['is_archived', 'status', 'updated_at'])
        messages.success(request, f"Завдання '{task.title}' заархівовано.")
    else:
        task.delete()
        messages.success(request, f"Завдання '{task.title}' видалено.")
    return redirect('tasks:task_list')


@login_required
def task_archive_list(request):
    user = request.user
    if not user.is_coordinator() and not user.is_superuser:
        messages.error(request, "Лише координатори можуть переглядати архів.")
        return redirect('tasks:task_list')
    if not user.is_superuser and not user.can_work():
        messages.warning(request, "Ваш акаунт очікує верифікації.")
        return redirect('accounts:pending_verification')

    verified_orgs = Organization.objects.filter(is_verified=True)

    if user.is_superuser:
        # Admins: full archive with optional org filter
        filter_applied = 'filter_applied' in request.GET
        selected_orgs = request.GET.getlist('org') if filter_applied else []
        org_q = _build_org_filter(selected_orgs, user)
        base_qs = Task.objects.filter(is_archived=True)
        if org_q is not None:
            base_qs = base_qs.filter(org_q)
    else:
        # Координатори бачать лише завдання, створені ними або їхньою організацією. Фільтр не показує, але все одно застосовуємо його для консистентності.
        selected_orgs = []
        if user.organization and user.organization.is_verified:
            base_qs = Task.objects.filter(
                is_archived=True,
                created_by__organization=user.organization,
            )
        else:
            base_qs = Task.objects.filter(is_archived=True, created_by=user)

    archived_tasks = base_qs.prefetch_related('assigned_volunteers', 'created_by__organization')
    return render(request, 'tasks/task_archive.html', {
        'archived_tasks': archived_tasks,
        'verified_orgs': verified_orgs if user.is_superuser else [],
        'selected_orgs': selected_orgs,
        'show_filter': user.is_superuser,
    })


@login_required
@require_POST
def task_accept(request, pk):
    """Волонтер приймає відкрите завдання — додається до assigned_volunteers."""
    task = get_object_or_404(Task, pk=pk)
    if not request.user.is_volunteer():
        messages.error(request, "Лише волонтери можуть брати завдання.")
        return redirect('tasks:task_detail', pk=pk)
    if task.status == Task.Status.COMPLETED or task.is_archived:
        messages.error(request, "Це завдання більше не приймає волонтерів.")
        return redirect('tasks:task_detail', pk=pk)
    if request.user in task.assigned_volunteers.all():
        messages.warning(request, "Ви вже прийняли це завдання.")
        return redirect('tasks:task_detail', pk=pk)
    if not task.slots_available:
        messages.error(request, "У цьому завданні немає вільних місць.")
        return redirect('tasks:task_detail', pk=pk)

    task.assigned_volunteers.add(request.user)
    task.status = Task.Status.IN_PROGRESS
    task.save(update_fields=['status', 'updated_at'])

    messages.success(request, f"Ви прийняли завдання '{task.title}'.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_unaccept(request, pk):
    """Волонтер відмовляється від прийнятого завдання."""
    task = get_object_or_404(Task, pk=pk)
    if not request.user.is_volunteer():
        messages.error(request, "Лише волонтери можуть відмовлятися від завдань.")
        return redirect('tasks:task_detail', pk=pk)
    if request.user not in task.assigned_volunteers.all():
        messages.warning(request, "Ви не приймали це завдання.")
        return redirect('tasks:task_detail', pk=pk)
    if task.status == Task.Status.COMPLETED:
        messages.error(request, "Неможливо відмовитися від завершеного завдання.")
        return redirect('tasks:task_detail', pk=pk)

    task.assigned_volunteers.remove(request.user)
    _revert_to_open_if_empty(task)
    messages.success(request, f"Ви відмовилися від завдання '{task.title}'.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_complete(request, pk):
    """Позначає завдання як завершене. Лише координатори можуть це зробити."""
    task = get_object_or_404(Task, pk=pk)
    user = request.user
    if not (user.is_coordinator() or user.is_superuser):
        messages.error(request, "Лише координатори можуть позначати завдання як завершені.")
        return redirect('tasks:task_detail', pk=pk)
    if not user.can_work():
        messages.warning(request, "Ваш акаунт очікує верифікації.")
        return redirect('accounts:pending_verification')
    if not user.can_manage_task(task):
        messages.error(request, "Ви можете завершувати лише завдання, створені вами або вашою організацією.")
        return redirect('tasks:task_detail', pk=pk)
    if task.status == Task.Status.COMPLETED:
        messages.warning(request, "Завдання вже завершено.")
        return redirect('tasks:task_detail', pk=pk)
    task.status = Task.Status.COMPLETED
    task.save()
    messages.success(request, f"Завдання '{task.title}' позначено як завершене.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def task_remove_volunteer(request, pk, vol_id):
    """Координатор видаляє конкретного волонтера із завдання."""
    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_coordinator() or request.user.is_superuser):
        messages.error(request, "Лише координатори можуть видаляти волонтерів.")
        return redirect('tasks:task_detail', pk=pk)
    if not request.user.can_manage_task(task):
        messages.error(request, "Ви можете керувати лише завданнями, створеними вами або вашою організацією.")
        return redirect('tasks:task_detail', pk=pk)
    if task.status == Task.Status.COMPLETED:
        messages.error(request, "Неможливо видалити волонтерів із завершеного завдання.")
        return redirect('tasks:task_detail', pk=pk)

    volunteer = get_object_or_404(task.assigned_volunteers, pk=vol_id)
    task.assigned_volunteers.remove(volunteer)
    _revert_to_open_if_empty(task)
    messages.success(request, f"{volunteer.username} видалено із завдання.")
    return redirect('tasks:task_detail', pk=pk)


@login_required
@require_POST
def update_location(request):
    """API-ендпоінт: волонтер надсилає поточні GPS-координати, вони зберігаються в сесії."""
    try:
        data = json.loads(request.body)
        lat = float(data['latitude'])
        lon = float(data['longitude'])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    source = data.get('source', 'gps')

    request.session['volunteer_lat'] = lat
    request.session['volunteer_lon'] = lon
    request.session['location_source'] = source

    if request.user.is_volunteer():
        profile, _ = VolunteerProfile.objects.get_or_create(user=request.user)
        profile.last_latitude = lat
        profile.last_longitude = lon
        profile.save(update_fields=['last_latitude', 'last_longitude', 'updated_at'])

    return JsonResponse({'status': 'ok', 'latitude': lat, 'longitude': lon})


@login_required
def tasks_geojson(request):
    """API-ендпоінт, що повертає всі видимі на карті завдання у форматі GeoJSON."""
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
