"""
Görselleştirme Katmanı — Akıllı Görev Önceliklendirme Sistemi

Üç grafik üretir:
    1. gantt_chart()       — Tek algoritmanın zaman planını Gantt chart olarak gösterir
    2. comparison_bar()    — 3 algoritmayı 3 metrik üzerinden karşılaştırır
    3. score_distribution()— Görevlerin skor dağılımını histogram olarak gösterir
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
import os

import matplotlib
matplotlib.use("Agg")          # ekransız ortam için
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator

from core.scheduler import ScheduleResult
from core.evaluator import EvaluationReport
from core.task import Task
from core.scorer import compute_score


# ── Renk paleti (algoritma bazlı) ─────────────────────────────────────
COLORS = {
    "greedy_edf": "#4A90D9",
    "random":     "#E07B4A",
    "fcfs":       "#5BBF8A",
    "skipped":    "#D0CFC8",
}

ALGO_LABELS = {
    "greedy_edf": "AI (Greedy+EDF)",
    "random":     "Random",
    "fcfs":       "FCFS",
}

METRIC_LABELS = {
    "completed_importance": "Toplam Önem Puanı (M1) ↑",
    "missed_deadlines":     "Kaçırılan Deadline (M2) ↓",
    "avg_urgency":          "Ort. Aciliyet (M3) ↑",
}


# ──────────────────────────────────────────────────────────────────────
# 1. Gantt Chart
# ──────────────────────────────────────────────────────────────────────

def gantt_chart(
    result: ScheduleResult,
    title: str = "Görev Planı",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    ScheduleResult için Gantt chart çizer.
    Her satır bir görev, x ekseni saat cinsinden zamanı gösterir.
    """
    fig, ax = plt.subplots(figsize=(12, max(4, len(result.scheduled) * 0.55 + 2)))

    color = COLORS.get(result.algorithm, "#4A90D9")
    algo_label = ALGO_LABELS.get(result.algorithm, result.algorithm)

    if not result.scheduled:
        ax.text(0.5, 0.5, "Planlanmış görev yok", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#888")
    else:
        start_ref = result.scheduled[0].start_time

        for i, s in enumerate(result.scheduled):
            x_start = (s.start_time - start_ref).total_seconds() / 3600
            x_dur   = s.task.duration
            y       = i

            # Ana blok
            ax.barh(y, x_dur, left=x_start, height=0.6,
                    color=color, alpha=0.85, edgecolor="white", linewidth=1.2)

            # Görev adı
            label = s.task.name if len(s.task.name) <= 20 else s.task.name[:18] + "…"
            ax.text(x_start + x_dur / 2, y, label,
                    ha="center", va="center", fontsize=8.5,
                    color="white", fontweight="bold")

            # Skor etiketi (sağda)
            ax.text(x_start + x_dur + 0.05, y, f"  skor: {s.score:.1f}",
                    va="center", fontsize=7.5, color="#555")

        # Atlanan görevler (gri, sağda)
        if result.skipped:
            skip_names = ", ".join(t.name for t in result.skipped[:4])
            if len(result.skipped) > 4:
                skip_names += f" +{len(result.skipped)-4}"
            ax.text(0.01, -0.10,
                    f"Atlanan ({len(result.skipped)}): {skip_names}",
                    transform=ax.transAxes, fontsize=8,
                    color="#999", style="italic")

        ax.set_yticks(range(len(result.scheduled)))
        ax.set_yticklabels(
            [f"{i+1}. {s.task.name}" for i, s in enumerate(result.scheduled)],
            fontsize=8.5,
        )
        ax.set_xlabel("Zaman (saat)", fontsize=10)
        ax.invert_yaxis()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis="x", linestyle="--", alpha=0.4)

    ax.set_title(f"{title}  —  {algo_label}", fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


# ──────────────────────────────────────────────────────────────────────
# 2. Karşılaştırma Bar Chart
# ──────────────────────────────────────────────────────────────────────

def comparison_bar(
    report: EvaluationReport,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    EvaluationReport için 3-metrik karşılaştırma grafiği.
    Her metrik ayrı subplot; 3 algoritma yan yana çubuk.
    """
    metrics_keys = ["completed_importance", "missed_deadlines", "avg_urgency"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        f"Algoritma Karşılaştırması — Senaryo: {report.scenario.upper()}",
        fontsize=13, fontweight="bold", y=1.02,
    )

    algos  = [m.algorithm for m in report.metrics]
    colors = [COLORS.get(a, "#999") for a in algos]
    xlabels = [ALGO_LABELS.get(a, a) for a in algos]

    for ax, key in zip(axes, metrics_keys):
        values = [getattr(m, key) for m in report.metrics]

        bars = ax.bar(xlabels, values, color=colors, edgecolor="white",
                      linewidth=1.2, width=0.55)

        # Değer etiketi (çubuğun üstüne)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                f"{val:.1f}" if isinstance(val, float) else str(val),
                ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

        ax.set_title(METRIC_LABELS[key], fontsize=9.5, pad=8)
        ax.set_ylim(0, max(values) * 1.25 + 0.5)
        ax.tick_params(axis="x", labelsize=8.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

        # Kazanan çubuğu hafifçe vurgula
        if key == "missed_deadlines":
            winner_idx = values.index(min(values))
        else:
            winner_idx = values.index(max(values))
        bars[winner_idx].set_edgecolor("#333")
        bars[winner_idx].set_linewidth(2.0)

    # Ortak renk açıklaması
    legend_patches = [
        mpatches.Patch(color=COLORS[a], label=ALGO_LABELS[a])
        for a in algos if a in COLORS
    ]
    fig.legend(handles=legend_patches, loc="lower center",
               ncol=3, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, -0.04))

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


# ──────────────────────────────────────────────────────────────────────
# 3. Skor Dağılımı Histogram
# ──────────────────────────────────────────────────────────────────────

def score_distribution(
    tasks: List[Task],
    title: str = "Görev Skor Dağılımı",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Görev listesinin heuristic skor dağılımını histogram olarak çizer.
    EDF boost alan görevler farklı renkte gösterilir.
    """
    scores_normal = [compute_score(t) for t in tasks if t.urgency < 4]
    scores_edf    = [compute_score(t) for t in tasks if t.urgency >= 4]

    fig, ax = plt.subplots(figsize=(9, 4.5))

    bins = 10
    if scores_normal:
        ax.hist(scores_normal, bins=bins, color=COLORS["fcfs"],
                alpha=0.75, label="Normal (urgency < 4)", edgecolor="white")
    if scores_edf:
        ax.hist(scores_edf, bins=bins, color=COLORS["greedy_edf"],
                alpha=0.75, label="EDF Boost (urgency ≥ 4)", edgecolor="white")

    ax.set_xlabel("Heuristic Skor", fontsize=10)
    ax.set_ylabel("Görev Sayısı",   fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


# ──────────────────────────────────────────────────────────────────────
# Toplu kayıt
# ──────────────────────────────────────────────────────────────────────

def save_all_charts(
    reports: dict,          # {scenario_name: EvaluationReport}
    output_dir: str = "outputs",
) -> List[str]:
    """
    Tüm senaryolar için comparison_bar ve gantt_chart'ları kaydeder.
    Kaydedilen dosya yollarının listesini döner.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved = []

    for name, report in reports.items():
        # Karşılaştırma bar chart
        path = os.path.join(output_dir, f"comparison_{name}.png")
        comparison_bar(report, save_path=path)
        plt.close("all")
        saved.append(path)

    return saved
