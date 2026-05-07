"""
Модуль алгоритмічного підбору завдань для волонтерів

Використовує угорський алгоритм (scipy.optimize.linear_sum_assignment) для обчислення
глобально оптимального розподілу волонтерів по завданнях із мінімізацією загальної вартості.

Функція вартості:
    C(i, j) = (w1 * distance_km(volunteer_i, task_j))
             - (w2 * priority(task_j))
             - (w3 * skill_match(volunteer_i, task_j))
             - (w4 * urgency(task_j))

Де:
    - w1 = MATCHING_WEIGHT_DISTANCE  (штрафує за відстань)
    - w2 = MATCHING_WEIGHT_PRIORITY  (нагороджує за вищий пріоритет завдання)
    - w3 = MATCHING_WEIGHT_SKILLS    (нагороджує за збіг навичок)
    - w4 = MATCHING_WEIGHT_URGENCY   (нагороджує завдання з близькою датою початку)
    - priority - {1, 2, 3}           (Низький, Середній, Високий)
    - skill_match = кількість навичок волонтера, які вимагає завдання
    - urgency - [0.0, 1.0]           (1.0 = починається сьогодні або вже розпочате,
                                       0.0 = починається через ≥ URGENCY_HORIZON_DAYS
                                       або дата початку не задана)

Стратегія ранжування (м'який розподіл):
    1. Запускаємо глобальний угорський алгоритм — отриманий розподіл для цього
       волонтера стає Рангом 1 («Найкращий вибір»), глобально оптимальним.
    2. Сортуємо всі завдання за індивідуальним рядком вартості волонтера (за зростанням).
       Ранг 2 та Ранг 3 — два найдешевших завдання, що не є Рангом 1.
    3. Повертаємо повний відсортований список, щоб вигляд міг упорядкувати завдання
       від найбільш до найменш рекомендованих.

Результат використовується для позначення та сортування завдань
в інтерфейсі, а не для примусового призначення, і відповідно зберігає автономію волонтера.
"""

import logging
from datetime import date
from typing import NamedTuple

import numpy as np
from geopy.distance import geodesic
from scipy.optimize import linear_sum_assignment
from django.conf import settings

logger = logging.getLogger(__name__)

# Завдання, що починаються протягом цієї кількості днів, вважаються терміновими.
URGENCY_HORIZON_DAYS = 14


class VolunteerInput(NamedTuple):
    user_id:   int
    latitude:  float
    longitude: float
    skill_ids: frozenset = frozenset()


class TaskInput(NamedTuple):
    task_id:            int
    latitude:           float
    longitude:          float
    priority:           int
    required_skill_ids: frozenset = frozenset()
    start_date:         date | None = None


class MatchResult(NamedTuple):
    volunteer_id: int
    task_id:      int
    cost:         float


def compute_distance_km(vol: VolunteerInput, task: TaskInput) -> float:
    """Обчислює геодезичну відстань у кілометрах між волонтером і завданням."""
    return geodesic((vol.latitude, vol.longitude), (task.latitude, task.longitude)).km


def compute_urgency(start_date: date | None, today: date) -> float:
    """
    Повертає показник терміновості в діапазоні [0.0, 1.0].

    1.0 — завдання починається сьогодні або вже розпочато
    0.0 — дата початку не задана або >= URGENCY_HORIZON_DAYS
    Лінійна інтерполяція між крайніми значеннями.
    """
    if start_date is None:
        return 0.0
    days_until = (start_date - today).days
    if days_until <= 0:
        return 1.0
    if days_until >= URGENCY_HORIZON_DAYS:
        return 0.0
    return 1.0 - days_until / URGENCY_HORIZON_DAYS


def build_cost_matrix(
    volunteers: list[VolunteerInput],
    tasks: list[TaskInput],
    w1: float,
    w2: float,
    w3: float,
    w4: float,
    today: date,
) -> np.ndarray:
    """
    Будує матрицю вартостей N×M, де:
        C[i][j] = w1 * distance_km(volunteer_i, task_j)
                - w2 * priority(task_j)
                - w3 * skill_match(volunteer_i, task_j)
                - w4 * urgency(task_j)
    """
    n = len(volunteers)
    m = len(tasks)
    matrix = np.zeros((n, m), dtype=float)
    for i, vol in enumerate(volunteers):
        for j, task in enumerate(tasks):
            distance    = compute_distance_km(vol, task)
            skill_match = len(vol.skill_ids & task.required_skill_ids)
            urgency     = compute_urgency(task.start_date, today)
            matrix[i][j] = (
                w1 * distance
                - w2 * task.priority
                - w3 * skill_match
                - w4 * urgency
            )
    return matrix


def run_matching(
    volunteers: list[VolunteerInput],
    tasks: list[TaskInput],
    today: date | None = None,
) -> list[MatchResult]:
    """
    Запускає угорський алгоритм для пошуку глобально оптимальних пар волонтер-завдання.
    Повертає список іменованих кортежів MatchResult.
    """
    if not volunteers or not tasks:
        return []

    if today is None:
        today = date.today()

    w1 = settings.MATCHING_WEIGHT_DISTANCE
    w2 = settings.MATCHING_WEIGHT_PRIORITY
    w3 = settings.MATCHING_WEIGHT_SKILLS
    w4 = getattr(settings, 'MATCHING_WEIGHT_URGENCY', 1.5)

    cost_matrix = build_cost_matrix(volunteers, tasks, w1, w2, w3, w4, today)
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    results = []
    for row, col in zip(row_indices, col_indices):
        results.append(MatchResult(
            volunteer_id=volunteers[row].user_id,
            task_id=tasks[col].task_id,
            cost=cost_matrix[row][col],
        ))
    logger.info(
        "Hungarian matching: %d volunteers × %d tasks → %d assignments",
        len(volunteers), len(tasks), len(results),
    )
    return results


def get_recommended_tasks_for_volunteer(
    volunteer_id: int,
    volunteer_lat: float,
    volunteer_lon: float,
    open_tasks,                              # QuerySet / список об'єктів Task з координатами
    volunteer_skill_ids: frozenset = frozenset(),
    all_active_volunteers=None,             # необов'язковий list[VolunteerInput] для глобальної оптимізації
    today: date | None = None,
) -> list[int]:
    """
    Повертає ідентифікатори завдань, відсортовані від найкращого до найгіршого збігу для цього волонтера.

    Ранг 1  — глобально оптимальний розподіл угорського алгоритму.
    Ранг 2+ — решта завдань, відсортованих за індивідуальною вартістю волонтера (за зростанням).

    Викликач може взяти [:3] для значків «Найкращий вибір / 2-й вибір / 3-й вибір» і
    використати повний список для сортування всіх завдань від найбільш до найменш рекомендованих.
    """
    if today is None:
        today = date.today()

    tasks_with_coords = [
        TaskInput(
            task_id=t.id,
            latitude=t.latitude,
            longitude=t.longitude,
            priority=t.priority,
            required_skill_ids=frozenset(t.required_skills.values_list('id', flat=True)),
            start_date=t.start_date,
        )
        for t in open_tasks
        if t.has_coordinates
    ]

    if not tasks_with_coords:
        return []

    w1 = settings.MATCHING_WEIGHT_DISTANCE
    w2 = settings.MATCHING_WEIGHT_PRIORITY
    w3 = settings.MATCHING_WEIGHT_SKILLS
    w4 = getattr(settings, 'MATCHING_WEIGHT_URGENCY', 1.5)

    current_vol = VolunteerInput(volunteer_id, volunteer_lat, volunteer_lon, volunteer_skill_ids)

    # Побудова персонального списку вартості для волонтера
    personal_costs = {}
    for task in tasks_with_coords:
        distance    = compute_distance_km(current_vol, task)
        skill_match = len(current_vol.skill_ids & task.required_skill_ids)
        urgency     = compute_urgency(task.start_date, today)
        personal_costs[task.task_id] = (
            w1 * distance
            - w2 * task.priority
            - w3 * skill_match
            - w4 * urgency
        )

    # Персональний ранкінг: всі завдання відсортовані за індивідуальною вартістю
    personal_ranking = sorted(personal_costs.keys(), key=lambda tid: personal_costs[tid])

    # Запускаємо глобальний угорський алгоритм.
    if all_active_volunteers:
        volunteers = list(all_active_volunteers)
        if not any(v.user_id == volunteer_id for v in volunteers):
            volunteers.append(current_vol)
    else:
        volunteers = [current_vol]

    matches = run_matching(volunteers, tasks_with_coords, today=today)
    hungarian_pick = next(
        (m.task_id for m in matches if m.volunteer_id == volunteer_id), None
    )

    # Створюємо остаточний впорядкований список: спочатку вибір угорського алгоритму, потім персональний порядок.
    if hungarian_pick and hungarian_pick in personal_costs:
        ordered = [hungarian_pick] + [tid for tid in personal_ranking if tid != hungarian_pick]
    else:
        ordered = personal_ranking

    logger.info(
        "Recommendations for volunteer %d: top-3 = %s",
        volunteer_id, ordered[:3],
    )
    return ordered
