"""
Модульні тести для модуля підбору за угорським алгоритмом.
"""
import pytest
import numpy as np
from datetime import date
from apps.tasks.services.matching import (
    VolunteerInput,
    TaskInput,
    build_cost_matrix,
    compute_distance_km,
    run_matching,
    get_recommended_tasks_for_volunteer,
)


# Тестові координати в районі Києва
VOL_KYIV_CENTRE = VolunteerInput(user_id=1, latitude=50.4501, longitude=30.5234)
TASK_NEAR = TaskInput(task_id=101, latitude=50.4520, longitude=30.5260, priority=2)
TASK_FAR = TaskInput(task_id=102, latitude=50.5500, longitude=30.7000, priority=1)
TASK_HIGH_PRIO_FAR = TaskInput(task_id=103, latitude=50.5600, longitude=30.7100, priority=3)


class TestDistanceComputation:
    def test_same_location_is_zero(self):
        vol = VolunteerInput(1, 50.0, 30.0)
        task = TaskInput(1, 50.0, 30.0, 2)
        assert compute_distance_km(vol, task) == pytest.approx(0.0, abs=0.001)

    def test_near_task_is_smaller_than_far(self):
        near = compute_distance_km(VOL_KYIV_CENTRE, TASK_NEAR)
        far = compute_distance_km(VOL_KYIV_CENTRE, TASK_FAR)
        assert near < far

    def test_distance_is_positive(self):
        d = compute_distance_km(VOL_KYIV_CENTRE, TASK_FAR)
        assert d > 0


class TestCostMatrix:
    TODAY = date.today()

    def test_shape(self):
        volunteers = [VOL_KYIV_CENTRE]
        tasks = [TASK_NEAR, TASK_FAR]
        matrix = build_cost_matrix(volunteers, tasks, w1=1.0, w2=2.0, w3=0.0, w4=0.0, today=self.TODAY)
        assert matrix.shape == (1, 2)

    def test_high_priority_lowers_cost(self):
        vol = VolunteerInput(1, 50.45, 30.52)
        # Однакова відстань, різні пріоритети
        task_low = TaskInput(1, 50.46, 30.53, priority=1)
        task_high = TaskInput(2, 50.46, 30.53, priority=3)
        matrix = build_cost_matrix([vol], [task_low, task_high], w1=1.0, w2=2.0, w3=0.0, w4=0.0, today=self.TODAY)
        # Високий пріоритет повинен мати меншу вартість (від'ємний внесок пріоритету)
        assert matrix[0][1] < matrix[0][0]

    def test_distance_increases_cost(self):
        volunteers = [VOL_KYIV_CENTRE]
        tasks = [TASK_NEAR, TASK_FAR]
        matrix = build_cost_matrix(volunteers, tasks, w1=1.0, w2=0.0, w3=0.0, w4=0.0, today=self.TODAY)
        # При w2=0 важлива лише відстань; ближче завдання повинно мати меншу вартість
        assert matrix[0][0] < matrix[0][1]


class TestRunMatching:
    def test_single_volunteer_single_task(self):
        results = run_matching([VOL_KYIV_CENTRE], [TASK_NEAR])
        assert len(results) == 1
        assert results[0].volunteer_id == 1
        assert results[0].task_id == 101

    def test_empty_inputs(self):
        assert run_matching([], [TASK_NEAR]) == []
        assert run_matching([VOL_KYIV_CENTRE], []) == []

    def test_more_tasks_than_volunteers(self):
        results = run_matching([VOL_KYIV_CENTRE], [TASK_NEAR, TASK_FAR, TASK_HIGH_PRIO_FAR])
        # 1 волонтер → не більше 1 призначення
        assert len(results) == 1

    def test_multiple_volunteers(self):
        vol2 = VolunteerInput(user_id=2, latitude=50.55, longitude=30.70)
        results = run_matching([VOL_KYIV_CENTRE, vol2], [TASK_NEAR, TASK_FAR])
        assert len(results) == 2
        assigned_volunteer_ids = {r.volunteer_id for r in results}
        assert 1 in assigned_volunteer_ids
        assert 2 in assigned_volunteer_ids

    def test_priority_influences_assignment(self):
        """
        Завдання з високим пріоритетом, що знаходиться далеко, все одно може бути
        призначене ближчому волонтеру залежно від конфігурації ваг.
        Перевіряємо, що результат є коректним призначенням (всі ID відповідають вхідним даним).
        """
        volunteers = [VOL_KYIV_CENTRE, VolunteerInput(2, 50.55, 30.70)]
        tasks = [TASK_NEAR, TASK_HIGH_PRIO_FAR]
        results = run_matching(volunteers, tasks)
        task_ids = {r.task_id for r in results}
        assert task_ids.issubset({TASK_NEAR.task_id, TASK_HIGH_PRIO_FAR.task_id})


class _EmptySkills:
    """Імітує порожній менеджер required_skills без звернення до БД."""
    def values_list(self, *args, **kwargs):
        return []


class TestGetRecommendedTasks:
    class MockTask:
        def __init__(self, task_id, lat, lon, priority):
            self.id = task_id
            self.latitude = lat
            self.longitude = lon
            self.priority = priority
            self.has_coordinates = True
            self.start_date = None
            self.required_skills = _EmptySkills()

    def test_returns_ordered_list_of_task_ids(self):
        tasks = [self.MockTask(1, 50.452, 30.524, 2), self.MockTask(2, 50.460, 30.530, 3)]
        result = get_recommended_tasks_for_volunteer(
            volunteer_id=99,
            volunteer_lat=50.4501,
            volunteer_lon=30.5234,
            open_tasks=tasks,
        )
        assert isinstance(result, list)
        assert set(result) == {1, 2}

    def test_empty_tasks_returns_empty_list(self):
        result = get_recommended_tasks_for_volunteer(99, 50.45, 30.52, [])
        assert result == []
