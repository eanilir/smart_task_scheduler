"""
Heuristic Skor Fonksiyonu — Akıllı Görev Önceliklendirme Sistemi

Skor formülü:
    score = (importance × 3) + (urgency × 5) + deadline_pressure - (duration × 0.5)

Katsayı mantığı:
    importance × 3   → önem orta ağırlıklı
    urgency    × 5   → aciliyet en belirleyici faktör
    deadline_pressure→ 1/(kalan_saat+1), yaklaştıkça artar
    duration  × 0.5  → uzun görev hafifçe cezalandırılır (küçük katsayı: overcorrect yok)

EDF Hibrit Boost:
    urgency >= 4 olan görevler +10 bonus alır.
    Bu; yüksek aciliyetli görevleri her koşulda listeye öne taşır —
    karmaşık interval scheduling olmadan EDF davranışını taklit eder.
"""

from __future__ import annotations
import heapq
from typing import List, Tuple

from core.task import Task


# ──────────────────────────────────────────────────────────────────────
# Sabitler — tek yerde tanımlı, test/raporda kolayca referans alınır
# ──────────────────────────────────────────────────────────────────────

W_IMPORTANCE   = 3.0   # önem ağırlığı
W_URGENCY      = 5.0   # aciliyet ağırlığı
W_DURATION     = 0.5   # süre cezası katsayısı
EDF_THRESHOLD  = 4     # bu urgency değeri ve üzeri → EDF boost
EDF_BOOST      = 10.0  # boost miktarı


# ──────────────────────────────────────────────────────────────────────
# Temel skor fonksiyonu
# ──────────────────────────────────────────────────────────────────────

def compute_score(task: Task) -> float:
    """
    Tek bir görev için heuristic skoru hesaplar.

    Dönüş değeri teorik aralık: yaklaşık -∞ … 40+
    Pratikte tipik aralık: 0 … 35 (EDF boost hariç)

    Örnek:
        Task(importance=5, urgency=5, duration=3, deadline=5 saat sonra)
        → (5×3) + (5×5) + 1/(5+1) - (3×0.5)
        → 15 + 25 + 0.167 - 1.5
        → 38.67   +10 EDF boost → 48.67
    """
    raw = (
        W_IMPORTANCE * task.importance
        + W_URGENCY  * task.urgency
        + task.deadline_pressure
        - W_DURATION * task.duration
    )

    # EDF Hibrit: yüksek aciliyetli görevleri öne taşı
    if task.urgency >= EDF_THRESHOLD:
        raw += EDF_BOOST

    return raw


# ──────────────────────────────────────────────────────────────────────
# Sıralama yardımcıları
# ──────────────────────────────────────────────────────────────────────

def rank_tasks(tasks: List[Task]) -> List[Tuple[float, Task]]:
    """
    Görev listesini skora göre azalan sırada döndürür.

    Dönüş: [(skor, task), ...] — en yüksek skor başta
    """
    scored = [(compute_score(t), t) for t in tasks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def top_k_tasks(tasks: List[Task], k: int) -> List[Tuple[float, Task]]:
    """
    En yüksek skorlu k görevi döndürür (heapq ile O(n log k)).

    k > len(tasks) ise tüm liste döner.
    """
    k = min(k, len(tasks))
    # heapq.nlargest negatif → büyükten küçüğe
    return heapq.nlargest(k, [(compute_score(t), t) for t in tasks],
                          key=lambda x: x[0])


# ──────────────────────────────────────────────────────────────────────
# Debug / rapor görüntüsü
# ──────────────────────────────────────────────────────────────────────

def score_breakdown(task: Task) -> str:
    """
    Skor bileşenlerini satır satır gösterir.
    Rapor ve Jupyter demo için kullanışlı.
    """
    imp_part  = W_IMPORTANCE * task.importance
    urg_part  = W_URGENCY    * task.urgency
    dl_part   = task.deadline_pressure
    dur_part  = W_DURATION   * task.duration
    boost     = EDF_BOOST if task.urgency >= EDF_THRESHOLD else 0.0
    total     = imp_part + urg_part + dl_part - dur_part + boost

    lines = [
        f"  Görev        : {task.name}",
        f"  Önem   ×{W_IMPORTANCE}  : {task.importance} × {W_IMPORTANCE} = {imp_part:.1f}",
        f"  Aciliyet×{W_URGENCY}  : {task.urgency} × {W_URGENCY} = {urg_part:.1f}",
        f"  Dl. baskısı  : {dl_part:.3f}",
        f"  Süre cezası  : -{task.duration} × {W_DURATION} = -{dur_part:.1f}",
    ]
    if boost:
        lines.append(f"  EDF boost    : +{boost:.1f}  (urgency ≥ {EDF_THRESHOLD})")
    lines.append(f"  {'─'*28}")
    lines.append(f"  TOPLAM SKOR  : {total:.3f}")
    return "\n".join(lines)


def print_ranking(tasks: List[Task]) -> None:
    """Sıralı listeyi konsola yazdırır — demo ve debug için."""
    ranked = rank_tasks(tasks)
    print(f"\n{'#':<4} {'Görev':<28} {'Skor':>7}  {'Acil':>5}  {'Önem':>5}  {'Süre':>6}  {'Kalan'}")
    print("─" * 72)
    for i, (score, task) in enumerate(ranked, 1):
        tl = task.time_left
        tl_str = f"{tl:.1f}h" if tl is not None else "  —  "
        edf_flag = " ⚡" if task.urgency >= EDF_THRESHOLD else ""
        print(
            f"{i:<4} {task.name:<28} {score:>7.2f}  "
            f"{task.urgency:>5}  {task.importance:>5}  "
            f"{task.duration:>5}h  {tl_str}{edf_flag}"
        )
    print()
