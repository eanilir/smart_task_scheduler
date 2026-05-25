from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.learning import (
    clear_active_tasks,
    db_path,
    init_db,
    insert_history_record,
    insert_task,
    list_all_records,
    rank_adaptively,
    update_task_status,
)
from core.task import Task, make_task
from core.learning import TaskRecord


BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = db_path(BASE_DIR)

app = FastAPI(title="Task Scheduler API")


class TaskCreate(BaseModel):
    name: str = Field(..., example="Write report")
    importance: int = Field(..., ge=1, le=5, example=3)
    urgency: int = Field(..., ge=1, le=5, example=4)
    duration: float = Field(..., gt=0, example=2.5)
    deadline_hours: Optional[float] = Field(None, example=48)
    category: Optional[str] = Field("genel")


class TaskOut(BaseModel):
    id: int
    name: str
    importance: int
    urgency: int
    duration: float
    category: str
    created_at: datetime
    deadline: Optional[datetime]
    baseline_score: float
    learned_bonus: float
    score: float


class LearningProfileOut(BaseModel):
    sample_size: int
    preferred_duration: float
    preferred_importance: float
    preferred_urgency: float
    completion_rate: float
    deletion_rate: float
    learning_rate: float
    noise: float
    category_weights: dict[str, float]
    hour_weights: dict[int, float]


class HistoricalTaskIn(BaseModel):
    name: str
    importance: int = Field(..., ge=1, le=5)
    urgency: int = Field(..., ge=1, le=5)
    duration: float = Field(..., gt=0)
    category: Optional[str] = Field("genel")
    deadline_hours: Optional[float] = Field(None)
    status: str = Field(..., pattern="^(completed|deleted)$")
    created_at: datetime
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


@app.on_event("startup")
def startup() -> None:
    init_db(DATABASE_FILE)


def _build_task_out(record: TaskRecord, baseline_score: float, learned_bonus: float, final_score: float) -> TaskOut:
    task = record.task
    return TaskOut(
        id=record.id,
        name=task.name,
        importance=task.importance,
        urgency=task.urgency,
        duration=task.duration,
        category=task.category,
        created_at=record.created_at,
        deadline=task.deadline,
        baseline_score=baseline_score,
        learned_bonus=learned_bonus,
        score=final_score,
    )


def _active_ranking() -> List[TaskOut]:
    records = list_all_records(DATABASE_FILE)
    ranked = rank_adaptively(records)
    output: List[TaskOut] = []
    for final_score, learned_bonus, record in ranked:
        baseline_score = final_score - learned_bonus
        output.append(_build_task_out(record, baseline_score, learned_bonus, final_score))
    return output


@app.post("/tasks", response_model=TaskOut)
def create_task(payload: TaskCreate):
    try:
        task = make_task(
            name=payload.name,
            importance=payload.importance,
            urgency=payload.urgency,
            duration=payload.duration,
            deadline_hours=payload.deadline_hours,
            category=payload.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Base score is stored immediately; learned ranking is recomputed from history.
    from core.scorer import compute_score

    baseline_score = compute_score(task)
    task_id = insert_task(DATABASE_FILE, task, baseline_score)

    records = list_all_records(DATABASE_FILE)
    ranked = rank_adaptively(records)
    for final_score, learned_bonus, record in ranked:
        if record.id == task_id:
            return _build_task_out(record, baseline_score, learned_bonus, final_score)

    # Fallback should not happen, but return a consistent payload if it does.
    return _build_task_out(
        TaskRecord(
            id=task_id,
            task=task,
            status="active",
            created_at=task.created_at,
            completed_at=None,
            deleted_at=None,
        ),
        baseline_score,
        0.0,
        baseline_score,
    )


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks():
    return _active_ranking()


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    if not update_task_status(DATABASE_FILE, task_id, "completed"):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "completed", "id": task_id}


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    if not update_task_status(DATABASE_FILE, task_id, "deleted"):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "id": task_id}


@app.delete("/tasks")
def clear_tasks():
    cleared = clear_active_tasks(DATABASE_FILE)
    return {"status": "archived", "cleared": cleared}


@app.get("/learning/profile", response_model=LearningProfileOut)
def learning_profile():
    records = list_all_records(DATABASE_FILE)
    from core.learning import build_habit_profile

    profile = build_habit_profile(records)
    return LearningProfileOut(
        sample_size=profile.sample_size,
        preferred_duration=profile.preferred_duration,
        preferred_importance=profile.preferred_importance,
        preferred_urgency=profile.preferred_urgency,
        completion_rate=profile.completion_rate,
        deletion_rate=profile.deletion_rate,
        learning_rate=profile.learning_rate,
        noise=profile.noise,
        category_weights=profile.category_weights,
        hour_weights=profile.hour_weights,
    )


@app.post("/history/import")
def import_history(records: List[HistoricalTaskIn]):
    imported_ids: List[int] = []
    for item in records:
        deadline = (
            item.created_at + timedelta(hours=item.deadline_hours)
            if item.deadline_hours is not None
            else None
        )
        task = Task(
            name=item.name,
            importance=item.importance,
            urgency=item.urgency,
            duration=item.duration,
            deadline=deadline,
            category=item.category or "genel",
            created_at=item.created_at,
        )
        imported_ids.append(
            insert_history_record(
                DATABASE_FILE,
                task,
                item.status,
                completed_at=item.completed_at,
                deleted_at=item.deleted_at,
            )
        )
    return {"status": "imported", "count": len(imported_ids), "ids": imported_ids}


# Serve the static UI after the API routes are declared.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
