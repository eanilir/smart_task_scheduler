"""
Evaluator — Akıllı Görev Önceliklendirme Sistemi

Üç algoritmayı (AI, Random, FCFS) aynı görev seti üzerinde çalıştırır
ve üç metrik ile karşılaştırır:

    M1 — completed_importance : Planlanan görevlerin toplam önem puanı
    M2 — missed_deadlines     : Kaçırılan deadline sayısı
    M3 — avg_urgency          : Planlanan görevlerin ortalama aciliyeti

Her senaryo (rahat / yogun / imkansiz) için ayrı EvaluationReport üretilir.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from core.scheduler import (
    ScheduleResult,
    schedule,
    schedule_random,
    schedule_fcfs,
)
from core.task import Task


# ──────────────────────────────────────────────────────────────────────
# Metrik hesaplama
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    """Tek bir algoritma çalışmasının ölçüm sonuçları."""
    algorithm: str
    completed_count: int      # planlanan görev sayısı
    skipped_count: int        # atlanan görev sayısı
    completed_importance: int # M1 — toplam önem puanı
    missed_deadlines: int     # M2 — deadline kaçırma
    avg_urgency: float        # M3 — ortalama aciliyet

    def as_dict(self) -> Dict[str, float | int | str]:
        return {
            "algorithm":            self.algorithm,
            "completed_count":      self.completed_count,
            "skipped_count":        self.skipped_count,
            "completed_importance": self.completed_importance,
            "missed_deadlines":     self.missed_deadlines,
            "avg_urgency":          round(self.avg_urgency, 2),
        }


def compute_metrics(result: ScheduleResult) -> Metrics:
    """ScheduleResult'tan Metrics nesnesi üretir."""
    scheduled = result.scheduled

    avg_urg = (
        sum(s.task.urgency for s in scheduled) / len(scheduled)
        if scheduled else 0.0
    )

    return Metrics(
        algorithm=result.algorithm,
        completed_count=len(scheduled),
        skipped_count=len(result.skipped),
        completed_importance=result.completed_importance,
        missed_deadlines=result.missed_deadlines,
        avg_urgency=avg_urg,
    )


# ──────────────────────────────────────────────────────────────────────
# Karşılaştırma raporu
# ──────────────────────────────────────────────────────────────────────

@dataclass
class EvaluationReport:
    """
    Bir senaryo üzerinde çalıştırılan üç algoritmanın karşılaştırma sonucu.
    viz/charts.py bu nesneyi doğrudan kullanır.
    """
    scenario: str
    metrics: List[Metrics] = field(default_factory=list)

    # ---- Kolay erişim ----

    def get(self, algorithm: str) -> Metrics | None:
        for m in self.metrics:
            if m.algorithm == algorithm:
                return m
        return None

    @property
    def algorithms(self) -> List[str]:
        return [m.algorithm for m in self.metrics]

    # ---- Kazanan tespiti ----

    def winner_importance(self) -> str:
        """M1: en yüksek completed_importance hangi algoritma?"""
        return max(self.metrics, key=lambda m: m.completed_importance).algorithm

    def winner_deadlines(self) -> str:
        """M2: en az missed_deadlines hangi algoritma?"""
        return min(self.metrics, key=lambda m: m.missed_deadlines).algorithm

    def winner_urgency(self) -> str:
        """M3: en yüksek avg_urgency hangi algoritma?"""
        return max(self.metrics, key=lambda m: m.avg_urgency).algorithm

    # ---- Konsol çıktısı ----

    def print_table(self) -> None:
        """Karşılaştırma tablosunu konsola yazdırır."""
        col = 14
        header = (
            f"{'Metrik':<26}"
            + "".join(f"{m.algorithm.upper():>{col}}" for m in self.metrics)
        )
        sep = "─" * len(header)

        rows = [
            ("Planlanan görev",      [m.completed_count      for m in self.metrics], ""),
            ("Atlanan görev",        [m.skipped_count        for m in self.metrics], ""),
            ("Toplam önem (M1) ↑",   [m.completed_importance for m in self.metrics], "int"),
            ("Kaçan deadline (M2) ↓",[m.missed_deadlines     for m in self.metrics], "int"),
            ("Ort. aciliyet (M3) ↑", [m.avg_urgency          for m in self.metrics], "float"),
        ]

        print(f"\n  Senaryo: {self.scenario.upper()}")
        print(f"  {sep}")
        print(f"  {header}")
        print(f"  {sep}")
        for label, values, fmt in rows:
            line = f"  {label:<26}"
            for v in values:
                cell = f"{v:.2f}" if fmt == "float" else str(v)
                line += f"{cell:>{col}}"
            print(line)
        print(f"  {sep}")

        print(f"\n  Kazananlar →  "
              f"M1: {self.winner_importance()}  |  "
              f"M2: {self.winner_deadlines()}  |  "
              f"M3: {self.winner_urgency()}")
        print()


# ──────────────────────────────────────────────────────────────────────
# Ana değerlendirme fonksiyonu
# ──────────────────────────────────────────────────────────────────────

def evaluate(
    tasks: List[Task],
    scenario_name: str = "bilinmiyor",
    available_hours: float = 8.0,
    start_time: datetime | None = None,
    random_seed: int = 42,
) -> EvaluationReport:
    """
    Aynı görev listesini üç algoritmayla çalıştırır ve rapor döner.

    Parametreler
    ------------
    tasks          : Değerlendirilecek görev listesi
    scenario_name  : Rapor başlığı için (ör. "yogun")
    available_hours: Toplam kullanılabilir süre
    start_time     : Başlangıç zamanı (None → datetime.now())
    random_seed    : Rastgele baseline tekrar üretilebilirliği için

    Kullanım
    --------
        from data.synthetic import load_scenario
        from core.evaluator import evaluate

        tasks  = load_scenario("yogun")
        report = evaluate(tasks, scenario_name="yogun")
        report.print_table()
    """
    if start_time is None:
        start_time = datetime.now()

    results = [
        schedule(tasks,        available_hours=available_hours, start_time=start_time),
        schedule_random(tasks, available_hours=available_hours, start_time=start_time, seed=random_seed),
        schedule_fcfs(tasks,   available_hours=available_hours, start_time=start_time),
    ]

    report = EvaluationReport(scenario=scenario_name)
    for r in results:
        report.metrics.append(compute_metrics(r))

    return report


def evaluate_all_scenarios(
    available_hours: float = 8.0,
    start_time: datetime | None = None,
) -> Dict[str, EvaluationReport]:
    """
    Üç senaryonun tamamını değerlendirir ve sözlük olarak döner.

    Kullanım
    --------
        from core.evaluator import evaluate_all_scenarios

        reports = evaluate_all_scenarios()
        for name, report in reports.items():
            report.print_table()
    """
    from data.synthetic import load_scenario

    reports = {}
    for name in ("rahat", "yogun", "imkansiz"):
        tasks = load_scenario(name, now=start_time)
        reports[name] = evaluate(
            tasks,
            scenario_name=name,
            available_hours=available_hours,
            start_time=start_time,
        )
    return reports
