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


@app.get("/evaluation")
def evaluate_test_set():
    """Evaluate on data/dataset_test_100.csv and return ROC AUC / AP and top picks.

    This avoids external ML deps by computing AUC/AP with pure Python.
    """
    import csv
    from pathlib import Path
    from datetime import datetime, timedelta

    base = Path(__file__).resolve().parent
    test_csv = base / "data" / "dataset_test_100.csv"
    if not test_csv.exists():
        return {"error": "test CSV not found", "path": str(test_csv)}

    # load training history and build combined records
    records = list_all_records(DATABASE_FILE)

    test_items = []
    with test_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            name = row.get("name") or f"test-{i}"
            importance = int(row.get("importance") or 3)
            urgency = int(row.get("urgency") or 3)
            duration = float(row.get("duration") or 1.0)
            category = row.get("category") or "genel"
            created_at = None
            if row.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(row["created_at"])
                except Exception:
                    created_at = datetime.now()
            else:
                created_at = datetime.now()

            dh = row.get("deadline_hours")
            deadline = None
            if dh and dh.strip() != "":
                try:
                    deadline = created_at + timedelta(hours=float(dh))
                except Exception:
                    deadline = None

            status = (row.get("status") or "deleted").strip()
            # create an ephemeral TaskRecord-like object using Task
            from core.task import Task
            t = Task(name=name, importance=importance, urgency=urgency, duration=duration, deadline=deadline, category=category, created_at=created_at)
            # fake id space to avoid colliding with DB ids
            fake_id = 1000000 + i
            from core.learning import TaskRecord as TR
            tr = TR(id=fake_id, task=t, status="active", created_at=created_at, completed_at=None, deleted_at=None)
            test_items.append((tr, 1 if status == "completed" else 0))

    combined = records + [tr for tr, _ in test_items]
    ranked = rank_adaptively(combined, iterations=128)

    # extract scores for test items
    scores = {}
    for final_score, learned_bonus, rec in ranked:
        if rec.id >= 1000000:
            scores[rec.id] = final_score

    # prepare labels and scores lists aligned
    y_true = []
    y_score = []
    for tr, label in test_items:
        y_true.append(label)
        y_score.append(scores.get(tr.id, 0.0))

    # compute AUC (Mann-Whitney U style) and average precision (AP)
    def auc_from_scores(y_true, y_score):
        # handle trivial cases
        n_pos = sum(1 for y in y_true if y == 1)
        n_neg = len(y_true) - n_pos
        if n_pos == 0 or n_neg == 0:
            return 0.0
        # rank scores
        paired = sorted(((s, y) for s, y in zip(y_score, y_true)), key=lambda x: x[0])
        ranks = list(range(1, len(paired) + 1))
        # sum ranks for positives
        sum_ranks_pos = sum(r for r, (_, y) in zip(ranks, paired) if y == 1)
        auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
        return auc

    def average_precision(y_true, y_score):
        # sort by score desc
        paired = sorted(((s, y) for s, y in zip(y_score, y_true)), key=lambda x: x[0], reverse=True)
        n_pos = sum(1 for _, y in paired if y == 1)
        if n_pos == 0:
            return 0.0
        tp = 0
        precisions = []
        for i, (_, y) in enumerate(paired, start=1):
            if y == 1:
                tp += 1
                precisions.append(tp / i)
        return sum(precisions) / n_pos if precisions else 0.0

    auc = auc_from_scores(y_true, y_score)
    ap = average_precision(y_true, y_score)

    # top 10 test picks
    top_test = sorted(((scores.get(tr.id, 0.0), tr.id, tr.task.name) for tr, _ in test_items), reverse=True)[:10]
    top_list = [{"id": tid, "name": name, "score": round(float(s), 3)} for s, tid, name in top_test]

    return {"auc": round(auc, 4), "average_precision": round(ap, 4), "top": top_list, "n_test": len(test_items)}


# Serve the static UI after the API routes are declared.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
