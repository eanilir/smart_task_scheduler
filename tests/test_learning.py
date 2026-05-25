"""Tests for the adaptive learning layer."""

from datetime import datetime, timedelta

from core.learning import HabitProfile, TaskRecord, build_habit_profile, rank_adaptively, simulate_learning_adjustments
from core.task import Task


def _record(task_id: int, name: str, category: str, status: str, created_offset_hours: float = 0.0, completed_offset_hours: float | None = None, deleted_offset_hours: float | None = None) -> TaskRecord:
    created_at = datetime.now() - timedelta(hours=created_offset_hours)
    task = Task(
        name=name,
        importance=3,
        urgency=3,
        duration=2.0,
        category=category,
        created_at=created_at,
    )
    completed_at = None if completed_offset_hours is None else datetime.now() - timedelta(hours=completed_offset_hours)
    deleted_at = None if deleted_offset_hours is None else datetime.now() - timedelta(hours=deleted_offset_hours)
    return TaskRecord(
        id=task_id,
        task=task,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        deleted_at=deleted_at,
    )


class TestHabitProfile:
    def test_build_habit_profile_uses_completion_and_deletion_history(self):
        records = [
            _record(1, "A", "is", "completed", completed_offset_hours=1),
            _record(2, "B", "hobi", "deleted", deleted_offset_hours=2),
        ]

        profile = build_habit_profile(records)

        assert profile.sample_size == 2
        assert profile.completion_rate == 0.5
        assert profile.deletion_rate == 0.5
        assert profile.category_weights["is"] > 0
        assert profile.category_weights["hobi"] < 0


class TestSimulation:
    def test_simulation_bonus_prefers_user_favorite_category(self):
        profile = HabitProfile(
            sample_size=12,
            preferred_duration=2.0,
            preferred_importance=3.0,
            preferred_urgency=3.0,
            category_weights={"is": 1.5, "hobi": -1.0},
            hour_weights={datetime.now().hour: 1.0},
            completion_rate=0.7,
            deletion_rate=0.3,
            noise=0.05,
            learning_rate=1.4,
        )

        active = [
            _record(10, "Favori", "is", "active"),
            _record(11, "Sevilmeyen", "hobi", "active"),
        ]

        bonuses = simulate_learning_adjustments(active, profile, iterations=48, hour=datetime.now().hour)

        assert bonuses[10] > bonuses[11]

    def test_rank_adaptively_orders_using_learned_preferences(self):
        records = [
            _record(1, "Geçmiş-1", "is", "completed", completed_offset_hours=1),
            _record(2, "Geçmiş-2", "is", "completed", completed_offset_hours=2),
            _record(3, "Silinen", "hobi", "deleted", deleted_offset_hours=3),
            _record(4, "Mevcut Favori", "is", "active"),
            _record(5, "Mevcut Zayıf", "hobi", "active"),
        ]

        ranked = rank_adaptively(records, iterations=48)

        assert ranked[0][2].id == 4
        assert ranked[-1][2].id == 5
