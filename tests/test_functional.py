"""
Unit-тести, що охоплюють основні функціональні вимоги платформи:

"""
import pytest
from django.test import Client

from apps.accounts.models import Organization, User
from apps.tasks.models import Task
from apps.volunteers.models import VolunteerProfile


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def _volunteer(username):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="pw",
        role=User.Role.VOLUNTEER,
        is_verified=True,
    )


def _coordinator(username, org=None, verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="pw",
        role=User.Role.COORDINATOR,
        is_verified=verified,
        organization=org,
    )


def _task(creator, **kwargs):
    return Task.objects.create(
        title="Test task",
        description="desc",
        address="Kyiv, Ukraine",
        created_by=creator,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Тест 1 — Реєстрація: волонтери автоматично верифікуються
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_volunteer_is_auto_verified():
    vol = _volunteer("vol1")
    assert vol.is_verified is True
    assert vol.can_work() is True


# ---------------------------------------------------------------------------
# Тест 2 — Неверифікований координатор не має доступу до платформи
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_unverified_coordinator_cannot_work():
    coord = _coordinator("coord_unverified", verified=False)
    assert coord.is_coordinator() is True
    assert coord.can_work() is False


# ---------------------------------------------------------------------------
# Тест 3 — Верифікація організації автоматично верифікує координаторів-членів
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_org_verification_cascades_to_coordinators():
    org = Organization.objects.create(name="Relief Org")
    coord = _coordinator("coord_cascade", org=org, verified=False)

    assert not coord.is_verified  # не верифікований до схвалення організації

    org.is_verified = True
    org.save()

    coord.refresh_from_db()
    assert coord.is_verified is True


# ---------------------------------------------------------------------------
# Тест 4 — Task.slots_available відображає наявність вільних місць
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_slots_available():
    coord = _coordinator("coord_slots")
    task = _task(coord, volunteers_needed=1)
    assert task.slots_available is True  # волонтерів ще немає

    vol = _volunteer("vol_slots")
    task.assigned_volunteers.add(vol)

    assert task.slots_available is False  # місце зайнято


# ---------------------------------------------------------------------------
# Тест 5 — Прийняття завдання переводить його статус у IN_PROGRESS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_accepting_task_sets_status_in_progress():
    coord = _coordinator("coord_accept")
    vol = _volunteer("vol_accept")
    task = _task(coord, volunteers_needed=2)
    assert task.status == Task.Status.OPEN

    client = Client()
    client.force_login(vol)
    client.post(f"/tasks/{task.pk}/accept/")

    task.refresh_from_db()
    assert task.status == Task.Status.IN_PROGRESS
    assert vol in task.assigned_volunteers.all()


# ---------------------------------------------------------------------------
# Тест 6 — Відмова останнього волонтера повертає статус завдання до OPEN
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_last_unaccept_reverts_task_to_open():
    coord = _coordinator("coord_unaccept")
    vol = _volunteer("vol_unaccept")
    task = _task(coord, volunteers_needed=2, status=Task.Status.IN_PROGRESS)
    task.assigned_volunteers.add(vol)

    client = Client()
    client.force_login(vol)
    client.post(f"/tasks/{task.pk}/unaccept/")

    task.refresh_from_db()
    assert task.status == Task.Status.OPEN
    assert vol not in task.assigned_volunteers.all()


# ---------------------------------------------------------------------------
# Тест 7 — Видалення завдання з призначеними волонтерами архівує його
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_delete_task_with_volunteers_archives_not_deletes():
    coord = _coordinator("coord_archive")
    vol = _volunteer("vol_archive")
    task = _task(coord, volunteers_needed=2, status=Task.Status.IN_PROGRESS)
    task.assigned_volunteers.add(vol)

    client = Client()
    client.force_login(coord)
    client.post(f"/tasks/{task.pk}/delete/")

    # Завдання має залишитись у БД, лише з позначкою архіву
    task.refresh_from_db()
    assert task.is_archived is True
    assert Task.objects.filter(pk=task.pk).exists()


# ---------------------------------------------------------------------------
# Тест 8 — VolunteerProfile.completed_tasks_count() рахує лише COMPLETED завдання
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_completed_tasks_count():
    coord = _coordinator("coord_count")
    vol = _volunteer("vol_count")
    profile = VolunteerProfile.objects.create(user=vol)

    open_task = _task(coord, status=Task.Status.OPEN)
    open_task.assigned_volunteers.add(vol)

    done1 = _task(coord, status=Task.Status.COMPLETED)
    done1.assigned_volunteers.add(vol)

    done2 = _task(coord, status=Task.Status.COMPLETED)
    done2.assigned_volunteers.add(vol)

    assert profile.completed_tasks_count() == 2
