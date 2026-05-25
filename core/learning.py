"""
Simulation-based adaptive learning for task ranking.

The module keeps a small SQLite-backed history of user actions and derives
habit signals from completed/deleted tasks. A Monte Carlo ranker then
adjusts the base heuristic score so the system can adapt to user preferences.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import random
import sqlite3
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.scorer import compute_score
from core.task import Task


DB_FILENAME = "task_scheduler.sqlite3"
DEFAULT_ITERATIONS = 64


@dataclass(frozen=True)
class HabitProfile:
    sample_size: int
    preferred_duration: float
    preferred_importance: float
    preferred_urgency: float
    category_weights: Dict[str, float]
    hour_weights: Dict[int, float]
    completion_rate: float
    deletion_rate: float
    noise: float
    learning_rate: float


@dataclass(frozen=True)
class TaskRecord:
    id: int
    task: Task
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    deleted_at: Optional[datetime]


def db_path(base_dir: Path) -> Path:
    return base_dir / "data" / DB_FILENAME


def connect(db_file: Path) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_file: Path) -> None:
    with connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                importance INTEGER NOT NULL,
                urgency INTEGER NOT NULL,
                duration REAL NOT NULL,
                deadline_at TEXT,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                completed_at TEXT,
                deleted_at TEXT,
                baseline_score REAL NOT NULL DEFAULT 0.0,
                learned_bonus REAL NOT NULL DEFAULT 0.0,
                final_score REAL NOT NULL DEFAULT 0.0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        conn.commit()


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _format_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _row_to_record(row: sqlite3.Row) -> TaskRecord:
    task = Task(
        name=row["name"],
        importance=row["importance"],
        urgency=row["urgency"],
        duration=row["duration"],
        deadline=_parse_datetime(row["deadline_at"]),
        category=row["category"],
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
    )
    return TaskRecord(
        id=row["id"],
        task=task,
        status=row["status"],
        created_at=_parse_datetime(row["created_at"]) or datetime.now(),
        completed_at=_parse_datetime(row["completed_at"]),
        deleted_at=_parse_datetime(row["deleted_at"]),
    )


def _fetch_rows(conn: sqlite3.Connection, where_sql: str = "", params: Sequence[object] = ()) -> List[TaskRecord]:
    query = "SELECT * FROM tasks"
    if where_sql:
        query += f" WHERE {where_sql}"
    query += " ORDER BY created_at ASC, id ASC"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_record(row) for row in rows]


def list_active_records(db_file: Path) -> List[TaskRecord]:
    with connect(db_file) as conn:
        return _fetch_rows(conn, "status = ?", ("active",))


def list_all_records(db_file: Path) -> List[TaskRecord]:
    with connect(db_file) as conn:
        return _fetch_rows(conn)


def insert_task(db_file: Path, task: Task, baseline_score: float) -> int:
    deadline_at = _format_datetime(task.deadline)
    created_at = _format_datetime(task.created_at)
    with connect(db_file) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                name, importance, urgency, duration, deadline_at,
                category, created_at, status, baseline_score,
                learned_bonus, final_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, 0.0, ?)
            """,
            (
                task.name,
                task.importance,
                task.urgency,
                task.duration,
                deadline_at,
                task.category,
                created_at,
                baseline_score,
                baseline_score,
            ),
        )
        task_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, created_at, payload) VALUES (?, ?, ?, ?)",
            (task_id, "created", created_at, json.dumps({"baseline_score": baseline_score})),
        )
        conn.commit()
        return task_id


def insert_history_record(
    db_file: Path,
    task: Task,
    status: str,
    baseline_score: float = 0.0,
    completed_at: Optional[datetime] = None,
    deleted_at: Optional[datetime] = None,
) -> int:
    if status not in {"completed", "deleted"}:
        raise ValueError(f"Historical records must be completed/deleted, got {status!r}")

    if status == "completed" and completed_at is None:
        completed_at = task.created_at
    if status == "deleted" and deleted_at is None:
        deleted_at = task.created_at

    deadline_at = _format_datetime(task.deadline)
    created_at = _format_datetime(task.created_at)
    with connect(db_file) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                name, importance, urgency, duration, deadline_at,
                category, created_at, status, completed_at, deleted_at,
                baseline_score, learned_bonus, final_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?)
            """,
            (
                task.name,
                task.importance,
                task.urgency,
                task.duration,
                deadline_at,
                task.category,
                created_at,
                status,
                _format_datetime(completed_at),
                _format_datetime(deleted_at),
                baseline_score,
                baseline_score,
            ),
        )
        task_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, created_at, payload) VALUES (?, ?, ?, ?)",
            (
                task_id,
                f"imported_{status}",
                (completed_at or deleted_at or task.created_at).isoformat(),
                json.dumps({"imported": True, "status": status}),
            ),
        )
        conn.commit()
        return task_id


def update_task_status(db_file: Path, task_id: int, status: str, timestamp: Optional[datetime] = None) -> bool:
    if status not in {"active", "completed", "deleted"}:
        raise ValueError(f"Unsupported status: {status}")

    timestamp = timestamp or datetime.now()
    column = "completed_at" if status == "completed" else "deleted_at" if status == "deleted" else None
    with connect(db_file) as conn:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return False

        if column is None:
            conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        else:
            conn.execute(
                f"UPDATE tasks SET status = ?, {column} = ? WHERE id = ?",
                (status, timestamp.isoformat(), task_id),
            )
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, created_at, payload) VALUES (?, ?, ?, ?)",
            (task_id, status, timestamp.isoformat(), None),
        )
        conn.commit()
        return True


def clear_active_tasks(db_file: Path) -> int:
    now = datetime.now().isoformat()
    with connect(db_file) as conn:
        rows = conn.execute("SELECT id FROM tasks WHERE status = 'active'").fetchall()
        task_ids = [int(row["id"]) for row in rows]
        conn.execute("UPDATE tasks SET status = 'deleted', deleted_at = ? WHERE status = 'active'", (now,))
        for task_id in task_ids:
            conn.execute(
                "INSERT INTO task_events (task_id, event_type, created_at, payload) VALUES (?, ?, ?, ?)",
                (task_id, "deleted", now, json.dumps({"bulk_clear": True})),
            )
        conn.commit()
        return len(task_ids)


def _normalize_counter(counter: Counter) -> Dict[str, float]:
    if not counter:
        return {}
    total = sum(counter.values())
    return {key: value / total for key, value in counter.items()}


def build_habit_profile(records: Sequence[TaskRecord]) -> HabitProfile:
    completed = [record for record in records if record.status == "completed"]
    deleted = [record for record in records if record.status == "deleted"]
    active = [record for record in records if record.status == "active"]
    historical = completed + deleted

    if not historical:
        return HabitProfile(
            sample_size=0,
            preferred_duration=1.0,
            preferred_importance=3.0,
            preferred_urgency=3.0,
            category_weights={},
            hour_weights={},
            completion_rate=0.0,
            deletion_rate=0.0,
            noise=1.0,
            learning_rate=0.0,
        )

    completion_counter = Counter(record.task.category for record in completed)
    deletion_counter = Counter(record.task.category for record in deleted)

    category_weights: Dict[str, float] = {}
    for category in set(completion_counter) | set(deletion_counter):
        completed_weight = completion_counter.get(category, 0)
        deleted_weight = deletion_counter.get(category, 0)
        category_weights[category] = (completed_weight - deleted_weight) / max(len(historical), 1)

    hour_counter = Counter()
    for record in historical:
        ts = record.completed_at or record.deleted_at or record.created_at
        hour_counter[ts.hour] += 1

    hour_weights = {
        hour: (count / len(historical))
        for hour, count in hour_counter.items()
    }

    preferred_duration = sum(record.task.duration for record in completed) / max(len(completed), 1)
    preferred_importance = sum(record.task.importance for record in completed) / max(len(completed), 1)
    preferred_urgency = sum(record.task.urgency for record in completed) / max(len(completed), 1)

    completion_rate = len(completed) / len(historical)
    deletion_rate = len(deleted) / len(historical)
    learning_rate = min(1.8, 0.25 + len(historical) * 0.04)
    noise = max(0.35, 1.2 - len(historical) * 0.03)

    return HabitProfile(
        sample_size=len(historical),
        preferred_duration=preferred_duration,
        preferred_importance=preferred_importance,
        preferred_urgency=preferred_urgency,
        category_weights=category_weights,
        hour_weights=hour_weights,
        completion_rate=completion_rate,
        deletion_rate=deletion_rate,
        noise=noise,
        learning_rate=learning_rate,
    )


def _habit_alignment(task: Task, profile: HabitProfile, hour: int) -> float:
    if profile.sample_size == 0:
        return 0.0

    category_bias = profile.category_weights.get(task.category, 0.0)
    duration_bias = math.exp(-abs(task.duration - profile.preferred_duration) / max(profile.preferred_duration, 1.0))
    importance_bias = math.exp(-abs(task.importance - profile.preferred_importance) / 2.0)
    urgency_bias = math.exp(-abs(task.urgency - profile.preferred_urgency) / 2.0)
    hour_bias = profile.hour_weights.get(hour, 0.0)
    overdue_bias = 0.35 if task.is_overdue else 0.0
    critical_bias = 0.2 if task.is_critical else 0.0

    return (
        category_bias * 2.5
        + duration_bias
        + importance_bias
        + urgency_bias
        + hour_bias
        + overdue_bias
        + critical_bias
    )


def _stable_seed(profile: HabitProfile, tasks: Sequence[TaskRecord], hour: int) -> int:
    payload = {
        "sample_size": profile.sample_size,
        "preferred_duration": round(profile.preferred_duration, 3),
        "preferred_importance": round(profile.preferred_importance, 3),
        "preferred_urgency": round(profile.preferred_urgency, 3),
        "hour": hour,
        "task_ids": [record.id for record in tasks],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def simulate_learning_adjustments(
    active_tasks: Sequence[TaskRecord],
    profile: HabitProfile,
    iterations: int = DEFAULT_ITERATIONS,
    hour: Optional[int] = None,
) -> Dict[int, float]:
    """
    Monte Carlo rank adjustment.

    Returns a task-id keyed bonus centered around zero. Higher values mean the
    learned profile thinks the task should float upward more often.
    """
    if not active_tasks:
        return {}

    hour = datetime.now().hour if hour is None else hour
    seed = _stable_seed(profile, active_tasks, hour)
    rng = random.Random(seed)

    baseline_scores = {record.id: compute_score(record.task) for record in active_tasks}
    habit_scores = {record.id: _habit_alignment(record.task, profile, hour) for record in active_tasks}
    task_ids = [record.id for record in active_tasks]
    bonuses = {task_id: 0.0 for task_id in task_ids}

    for _ in range(max(iterations, 1)):
        utilities = []
        for record in active_tasks:
            utility = (
                baseline_scores[record.id]
                + profile.learning_rate * habit_scores[record.id]
                + rng.gauss(0.0, profile.noise)
            )
            utilities.append((utility, record.id))

        utilities.sort(key=lambda item: item[0], reverse=True)
        total = len(utilities)
        if total == 1:
            bonuses[utilities[0][1]] += 1.0
            continue

        for rank, (_, task_id) in enumerate(utilities):
            position_score = 1.0 - (rank / (total - 1))
            bonuses[task_id] += position_score

    for task_id in bonuses:
        average_position = bonuses[task_id] / max(iterations, 1)
        centered = average_position - 0.5
        bonuses[task_id] = centered * (2.0 + profile.learning_rate)

    return bonuses


def rank_adaptively(records: Sequence[TaskRecord], iterations: int = DEFAULT_ITERATIONS) -> List[Tuple[float, float, TaskRecord]]:
    """Return [(final_score, learned_bonus, record), ...] ordered descending."""
    active_records = [record for record in records if record.status == "active"]
    if not active_records:
        return []

    profile = build_habit_profile(records)
    bonuses = simulate_learning_adjustments(active_records, profile, iterations=iterations)
    ranked: List[Tuple[float, float, TaskRecord]] = []
    for record in active_records:
        baseline = compute_score(record.task)
        learned_bonus = bonuses.get(record.id, 0.0)
        final_score = baseline + learned_bonus
        ranked.append((final_score, learned_bonus, record))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def task_record_summary(record: TaskRecord) -> Dict[str, object]:
    return {
        "id": record.id,
        "name": record.task.name,
        "importance": record.task.importance,
        "urgency": record.task.urgency,
        "duration": record.task.duration,
        "category": record.task.category,
        "created_at": record.created_at,
        "deadline": record.task.deadline,
        "status": record.status,
    }
