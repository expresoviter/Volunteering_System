"""
Algorithmic Task-to-Volunteer Matching Module
=============================================
Uses the Hungarian algorithm (scipy.optimize.linear_sum_assignment) to compute
the globally optimal assignment of volunteers to tasks, minimising total cost.

Cost function:
    C(i, j) = (w1 * distance_km(volunteer_i, task_j))
             - (w2 * priority(task_j))
             - (w3 * skill_match(volunteer_i, task_j))
             - (w4 * urgency(task_j))

Where:
    - w1 = MATCHING_WEIGHT_DISTANCE  (penalises distance)
    - w2 = MATCHING_WEIGHT_PRIORITY  (rewards higher-priority tasks)
    - w3 = MATCHING_WEIGHT_SKILLS    (rewards skill overlap)
    - w4 = MATCHING_WEIGHT_URGENCY   (rewards tasks whose start date is soon)
    - priority ∈ {1, 2, 3}           (Low, Medium, High)
    - skill_match = number of skills the volunteer has that the task requires
    - urgency ∈ [0.0, 1.0]           (1.0 = starts today or already started,
                                       0.0 = starts ≥ URGENCY_HORIZON_DAYS away
                                       or no start date set)

Ranking strategy (soft assignment):
    1. Run the global Hungarian algorithm — the resulting assignment for this
       volunteer becomes Rank 1 ("Top Pick"), the globally optimal choice.
    2. Sort all tasks by this volunteer's individual cost row (ascending).
       Rank 2 and Rank 3 are the two cheapest tasks that are not Rank 1.
    3. Return the full sorted list so the view can order tasks from most to
       least recommended.

THESIS-NOTE: The result is used to tag and sort tasks in the UI rather than
forcibly assigning them, preserving volunteer autonomy.
"""

import logging
from datetime import date
from typing import NamedTuple

import numpy as np
from geopy.distance import geodesic
from scipy.optimize import linear_sum_assignment
from django.conf import settings

logger = logging.getLogger(__name__)

# Tasks starting within this many days are considered urgent.
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
    """Compute geodesic distance in kilometres between a volunteer and a task."""
    return geodesic((vol.latitude, vol.longitude), (task.latitude, task.longitude)).km


def compute_urgency(start_date: date | None, today: date) -> float:
    """
    Return an urgency score in [0.0, 1.0].

    1.0 — task starts today or has already started
    0.0 — no start date, or start date is >= URGENCY_HORIZON_DAYS away
    Linear interpolation in between.
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
    Build the N×M cost matrix where:
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
    Run the Hungarian algorithm to find the globally optimal volunteer-task pairs.
    Returns a list of MatchResult named tuples.
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
    open_tasks,                              # QuerySet / list of Task objects with coordinates
    volunteer_skill_ids: frozenset = frozenset(),
    all_active_volunteers=None,             # optional list[VolunteerInput] for global optimisation
    today: date | None = None,
) -> list[int]:
    """
    Return task IDs ordered from best to worst match for this volunteer.

    Rank 1  — globally optimal assignment from the Hungarian algorithm.
    Rank 2+ — remaining tasks sorted by this volunteer's individual cost (ascending).

    The caller can take [:3] for the "Top Pick / 2nd Pick / 3rd Pick" badges and
    use the full list to sort all tasks from most to least recommended.
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

    # Build personal cost row (1 volunteer × all tasks) for full ranking.
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

    # Personal ranking: all tasks sorted by individual cost, best first.
    personal_ranking = sorted(personal_costs.keys(), key=lambda tid: personal_costs[tid])

    # Run global Hungarian to determine Rank 1 (globally optimal pick).
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

    # Compose final ordered list: Hungarian pick first, then personal order.
    if hungarian_pick and hungarian_pick in personal_costs:
        ordered = [hungarian_pick] + [tid for tid in personal_ranking if tid != hungarian_pick]
    else:
        ordered = personal_ranking

    logger.info(
        "Recommendations for volunteer %d: top-3 = %s",
        volunteer_id, ordered[:3],
    )
    return ordered
