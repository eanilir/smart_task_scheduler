"""
Greedy + EDF Hibrit Zamanlayıcı — Akıllı Görev Önceliklendirme Sistemi

Algoritma 3 aşamada çalışır:
    1. Skorla   : Her görev için heuristic skor hesaplanır
    2. Sırala   : Görevler skora göre azalan sırada dizilir
    3. Yerleştir: Görev mevcut zamana sığıyorsa planla, sığmıyorsa atla

Conflict handling: swap veya backtrack yok.
    if current_time + task.duration > deadline → görevi atla
Bu kural kasıtlı olarak basit tutulmuştur.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from core.task import Task
from core.scorer import rank_tasks


# ──────────────────────────────────────────────────────────────────────
# Sonuç veri yapıları
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ScheduledTask:
    """Planlanmış bir görevi zaman dilimi bilgisiyle temsil eder."""
    task: Task
    start_time: datetime
    end_time: datetime
    score: float

    @property
    def duration_hours(self) -> float:
        return (self.end_time - self.start_time).total_seconds() / 3600

    def __repr__(self) -> str:
        return (
            f"ScheduledTask({self.task.name!r}, "
            f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}, "
            f"skor={self.score:.2f})"
        )


@dataclass
class ScheduleResult:
    """
    Zamanlayıcının ürettiği tam sonucu tutar.
    Evaluator bu nesneyi girdi olarak kullanır.
    """
    scheduled: List[ScheduledTask] = field(default_factory=list)
    skipped: List[Task]            = field(default_factory=list)
    algorithm: str                 = "greedy_edf"

    @property
    def total_score(self) -> float:
        return sum(s.score for s in self.scheduled)

    @property
    def missed_deadlines(self) -> int:
        """Planlanan görevler arasında deadline'ı geçmiş olanlar."""
        return sum(1 for s in self.scheduled if s.task.is_overdue)

    @property
    def completed_importance(self) -> int:
        """Planlanan görevlerin toplam önem puanı."""
        return sum(s.task.importance for s in self.scheduled)

    def summary(self) -> str:
        lines = [
            f"Algoritma      : {self.algorithm}",
            f"Planlanan      : {len(self.scheduled)} görev",
            f"Atlanan        : {len(self.skipped)} görev",
            f"Toplam skor    : {self.total_score:.2f}",
            f"Toplam önem    : {self.completed_importance}",
            f"Kaçan deadline : {self.missed_deadlines}",
        ]
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Ana zamanlayıcı
# ──────────────────────────────────────────────────────────────────────

def schedule(
    tasks: List[Task],
    available_hours: float = 8.0,
    start_time: Optional[datetime] = None,
) -> ScheduleResult:
    """
    Görev listesini Greedy + EDF hibrit algoritmasıyla planlar.

    Parametreler
    ------------
    tasks           : Planlanacak görev listesi
    available_hours : Kullanılabilir toplam süre (varsayılan 8 saat)
    start_time      : Başlangıç zamanı (varsayılan: şu an)

    Dönüş
    -----
    ScheduleResult  : Planlanan ve atlanan görevleri içerir
    """
    if start_time is None:
        start_time = datetime.now()

    result      = ScheduleResult(algorithm="greedy_edf")
    current     = start_time
    time_budget = available_hours  # kalan saat

    # Görevleri heuristic skora göre sırala (scorer.py)
    ranked = rank_tasks(tasks)

    for score, task in ranked:

        # Zaman bütçesi dolmuşsa kalan görevleri atla
        if time_budget <= 0:
            result.skipped.append(task)
            continue

        # Görev mevcut zaman dilimine sığmıyor mu?
        if task.duration > time_budget:
            result.skipped.append(task)
            continue

        # Deadline kontrolü: görev bitişi deadline'ı geçiyor mu?
        end = current + timedelta(hours=task.duration)
        if task.deadline is not None and end > task.deadline:
            result.skipped.append(task)
            continue

        # Görevi planla
        result.scheduled.append(
            ScheduledTask(task=task, start_time=current, end_time=end, score=score)
        )
        current     = end
        time_budget -= task.duration

    return result


# ──────────────────────────────────────────────────────────────────────
# Baseline algoritmaları (evaluator karşılaştırması için)
# ──────────────────────────────────────────────────────────────────────

def schedule_random(
    tasks: List[Task],
    available_hours: float = 8.0,
    start_time: Optional[datetime] = None,
    seed: int = 42,
) -> ScheduleResult:
    """
    Baseline 1 — Rastgele sıralama.
    Görevleri karıştırır, ardından aynı sığdırma kuralını uygular.
    """
    import random
    rng = random.Random(seed)

    shuffled = tasks[:]
    rng.shuffle(shuffled)

    if start_time is None:
        start_time = datetime.now()

    result      = ScheduleResult(algorithm="random")
    current     = start_time
    time_budget = available_hours

    for task in shuffled:
        if time_budget <= 0 or task.duration > time_budget:
            result.skipped.append(task)
            continue
        end = current + timedelta(hours=task.duration)
        if task.deadline is not None and end > task.deadline:
            result.skipped.append(task)
            continue
        result.scheduled.append(
            ScheduledTask(task=task, start_time=current, end_time=end, score=0.0)
        )
        current     = end
        time_budget -= task.duration

    return result


def schedule_fcfs(
    tasks: List[Task],
    available_hours: float = 8.0,
    start_time: Optional[datetime] = None,
) -> ScheduleResult:
    """
    Baseline 2 — First Come First Served.
    Görevleri oluşturulma sırasına (created_at) göre planlar.
    """
    ordered = sorted(tasks, key=lambda t: t.created_at)

    if start_time is None:
        start_time = datetime.now()

    result      = ScheduleResult(algorithm="fcfs")
    current     = start_time
    time_budget = available_hours

    for task in ordered:
        if time_budget <= 0 or task.duration > time_budget:
            result.skipped.append(task)
            continue
        end = current + timedelta(hours=task.duration)
        if task.deadline is not None and end > task.deadline:
            result.skipped.append(task)
            continue
        result.scheduled.append(
            ScheduledTask(task=task, start_time=current, end_time=end, score=0.0)
        )
        current     = end
        time_budget -= task.duration

    return result
