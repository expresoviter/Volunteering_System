"""
Algorithmic Task-to-Volunteer Matching Module
=============================================
Uses the Hungarian algorithm (scipy.optimize.linear_sum_assignment) to compute
the globally optimal assignment of volunteers to tasks, minimizing total cost.

Cost function:
    C(i, j) = (w1 * distance_km(volunteer_i, task_j)) - (w2 * priority(task_j))

Where:
    - w1 = MATCHING_WEIGHT_DISTANCE (penalizes distance)
    - w2 = MATCHING_WEIGHT_PRIORITY (rewards higher-priority tasks)
    - priority ∈ {1, 2, 3} (Low, Medium, High)

THESIS-NOTE: This is a "soft" assignment — the result is used to tag tasks as
"Recommended" in the UI rather than forcibly assigning them, preserving volunteer
autonomy while surfacing the optimal choices.
"""

import logging
from typing import NamedTuple

import numpy as np
from geopy.distance import geodesic
from scipy.optimize import linear_sum_assignment
from django.conf import settings

logger = logging.getLogger(__name__)


class VolunteerInput(NamedTuple):
    user_id: int
    latitude: float
    longitude: float


class TaskInput(NamedTuple):
    task_id: int
    latitude: float
    longitude: float
    priority: int


class MatchResult(NamedTuple):
    volunteer_id: int
    task_id: int
    cost: float


def compute_distance_km(vol: VolunteerInput, task: TaskInput) -> float:
    """Compute geodesic distance in kilometres between a volunteer and a task."""
    return geodesic((vol.latitude, vol.longitude), (task.latitude, task.longitude)).km


def build_cost_matrix(
    volunteers: list[VolunteerInput],
    tasks: list[TaskInput],
    w1: float,
    w2: float,
) -> np.ndarray:
    """
    Build the N×M cost matrix where:
        C[i][j] = w1 * distance_km(volunteer_i, task_j) - w2 * priority(task_j)

    The matrix is padded with zeros if N < M so that scipy can handle the
    rectangular case (more tasks than volunteers).
    """
    n = len(volunteers)
    m = len(tasks)
    # Pad to square if needed — scipy handles rectangular matrices since 0.17
    matrix = np.zeros((n, m), dtype=float)
    for i, vol in enumerate(volunteers):
        for j, task in enumerate(tasks):
            distance = compute_distance_km(vol, task)
            matrix[i][j] = (w1 * distance) - (w2 * task.priority)
    return matrix


def run_matching(
    volunteers: list[VolunteerInput],
    tasks: list[TaskInput],
) -> list[MatchResult]:
    """
    Run the Hungarian algorithm to find the globally optimal volunteer-task pairs.

    Returns a list of MatchResult named tuples.
    """
    if not volunteers or not tasks:
        return []

    w1 = settings.MATCHING_WEIGHT_DISTANCE
    w2 = settings.MATCHING_WEIGHT_PRIORITY

    cost_matrix = build_cost_matrix(volunteers, tasks, w1, w2)
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    results = []
    for row, col in zip(row_indices, col_indices):
        results.append(
            MatchResult(
                volunteer_id=volunteers[row].user_id,
                task_id=tasks[col].task_id,
                cost=cost_matrix[row][col],
            )
        )
    logger.info(
        "Hungarian matching: %d volunteers × %d tasks → %d assignments",
        len(volunteers), len(tasks), len(results),
    )
    return results


def get_recommended_tasks_for_volunteer(
    volunteer_id: int,
    volunteer_lat: float,
    volunteer_lon: float,
    open_tasks,  # QuerySet of Task objects with coordinates
    all_active_volunteers=None,  # optional list of VolunteerInput for global optimisation
) -> set[int]:
    """
    Return a set of task IDs that the Hungarian algorithm recommends for this volunteer.

    If other active volunteer locations are known, they are included in the global
    optimisation. Otherwise only the current volunteer is used (N=1 case).
    """
    tasks_with_coords = [
        TaskInput(task_id=t.id, latitude=t.latitude, longitude=t.longitude, priority=t.priority)
        for t in open_tasks
        if t.has_coordinates
    ]

    if not tasks_with_coords:
        return set()

    if all_active_volunteers:
        volunteers = list(all_active_volunteers)
        # Ensure the current volunteer is included
        if not any(v.user_id == volunteer_id for v in volunteers):
            volunteers.append(VolunteerInput(volunteer_id, volunteer_lat, volunteer_lon))
    else:
        volunteers = [VolunteerInput(volunteer_id, volunteer_lat, volunteer_lon)]

    matches = run_matching(volunteers, tasks_with_coords)
    return {m.task_id for m in matches if m.volunteer_id == volunteer_id}
