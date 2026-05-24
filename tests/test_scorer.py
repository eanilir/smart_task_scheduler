"""
scorer.py için birim testler
Çalıştır: pytest tests/test_scorer.py -v
"""

import pytest
from core.task import Task, make_task
from core.scorer import (
    compute_score, rank_tasks, top_k_tasks, score_breakdown,
    W_IMPORTANCE, W_URGENCY, W_DURATION, EDF_BOOST, EDF_THRESHOLD,
)


# ──────────────────────────────────────────────
# 1. compute_score — temel hesaplama
# ──────────────────────────────────────────────

class TestComputeScore:

    def test_no_deadline_no_boost(self):
        """Deadline yok, urgency < 4 → saf formül."""
        t = Task(name="X", importance=3, urgency=2, duration=2.0)
        expected = W_IMPORTANCE * 3 + W_URGENCY * 2 + 0.0 - W_DURATION * 2.0
        assert compute_score(t) == pytest.approx(expected)

    def test_edf_boost_applied_when_urgency_gte_threshold(self):
        """urgency == 4 → EDF boost eklenmeli."""
        t = Task(name="X", importance=1, urgency=4, duration=1.0)
        score_with_boost    = compute_score(t)
        expected_no_boost   = W_IMPORTANCE * 1 + W_URGENCY * 4 - W_DURATION * 1.0
        assert score_with_boost == pytest.approx(expected_no_boost + EDF_BOOST)

    def test_edf_boost_not_applied_below_threshold(self):
        """urgency == EDF_THRESHOLD - 1 → boost yok."""
        t = Task(name="X", importance=1, urgency=EDF_THRESHOLD - 1, duration=1.0)
        expected = W_IMPORTANCE * 1 + W_URGENCY * (EDF_THRESHOLD - 1) - W_DURATION * 1.0
        assert compute_score(t) == pytest.approx(expected)

    def test_deadline_pressure_included(self):
        """Deadline olan görevin skoru, olmayana göre yüksek olmalı."""
        no_dl   = Task(name="A", importance=3, urgency=3, duration=1.0)
        with_dl = make_task("B", 3, 3, 1.0, deadline_hours=5)
        assert compute_score(with_dl) > compute_score(no_dl)

    def test_longer_duration_lowers_score(self):
        """Diğer her şey eşit, daha uzun görev daha düşük skor almalı."""
        short = Task(name="A", importance=3, urgency=3, duration=1.0)
        long_ = Task(name="B", importance=3, urgency=3, duration=5.0)
        assert compute_score(short) > compute_score(long_)

    def test_higher_importance_raises_score(self):
        low_imp  = Task(name="A", importance=1, urgency=2, duration=1.0)
        high_imp = Task(name="B", importance=5, urgency=2, duration=1.0)
        assert compute_score(high_imp) > compute_score(low_imp)

    def test_higher_urgency_raises_score_more_than_importance(self):
        """
        urgency katsayısı (5) > importance katsayısı (3) olduğu için
        +1 urgency, +1 importance'dan daha fazla skor artırmalı.
        """
        base     = Task(name="X", importance=2, urgency=2, duration=1.0)
        more_imp = Task(name="Y", importance=3, urgency=2, duration=1.0)
        more_urg = Task(name="Z", importance=2, urgency=3, duration=1.0)
        delta_imp = compute_score(more_imp) - compute_score(base)
        delta_urg = compute_score(more_urg) - compute_score(base)
        assert delta_urg > delta_imp


# ──────────────────────────────────────────────
# 2. rank_tasks — sıralama
# ──────────────────────────────────────────────

class TestRankTasks:

    def _sample_tasks(self):
        return [
            Task(name="Düşük",   importance=1, urgency=1, duration=1.0),
            Task(name="Orta",    importance=3, urgency=3, duration=1.0),
            Task(name="Yüksek",  importance=5, urgency=5, duration=1.0),
        ]

    def test_returns_descending_order(self):
        ranked = rank_tasks(self._sample_tasks())
        scores = [s for s, _ in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_highest_score_first(self):
        ranked = rank_tasks(self._sample_tasks())
        assert ranked[0][1].name == "Yüksek"

    def test_lowest_score_last(self):
        ranked = rank_tasks(self._sample_tasks())
        assert ranked[-1][1].name == "Düşük"

    def test_empty_list_returns_empty(self):
        assert rank_tasks([]) == []

    def test_single_task(self):
        t = Task(name="Tek", importance=3, urgency=3, duration=1.0)
        ranked = rank_tasks([t])
        assert len(ranked) == 1
        assert ranked[0][1].name == "Tek"

    def test_edf_task_beats_low_urgency(self):
        """EDF boost alan görev, düşük urgency'li önemli görevi geçmeli."""
        edf_task  = Task(name="EDF",   importance=2, urgency=4, duration=1.0)
        high_imp  = Task(name="Önemli", importance=5, urgency=2, duration=1.0)
        ranked = rank_tasks([high_imp, edf_task])
        assert ranked[0][1].name == "EDF"


# ──────────────────────────────────────────────
# 3. top_k_tasks
# ──────────────────────────────────────────────

class TestTopKTasks:

    def _tasks(self, n=5):
        return [
            Task(name=f"Görev{i}", importance=i, urgency=i, duration=1.0)
            for i in range(1, n + 1)
        ]

    def test_returns_k_items(self):
        assert len(top_k_tasks(self._tasks(), 3)) == 3

    def test_returns_all_when_k_exceeds_list(self):
        tasks = self._tasks(3)
        assert len(top_k_tasks(tasks, 10)) == 3

    def test_top_item_has_highest_score(self):
        result = top_k_tasks(self._tasks(), 2)
        scores = [s for s, _ in result]
        assert scores[0] == max(scores)

    def test_k_zero_returns_empty(self):
        assert top_k_tasks(self._tasks(), 0) == []


# ──────────────────────────────────────────────
# 4. score_breakdown
# ──────────────────────────────────────────────

class TestScoreBreakdown:

    def test_contains_task_name(self):
        t = Task(name="Matematik", importance=4, urgency=3, duration=2.0)
        assert "Matematik" in score_breakdown(t)

    def test_contains_total_label(self):
        t = Task(name="X", importance=2, urgency=2, duration=1.0)
        assert "TOPLAM" in score_breakdown(t)

    def test_edf_boost_line_present_when_applicable(self):
        t = Task(name="X", importance=1, urgency=5, duration=1.0)
        assert "EDF boost" in score_breakdown(t)

    def test_edf_boost_line_absent_when_not_applicable(self):
        t = Task(name="X", importance=1, urgency=2, duration=1.0)
        assert "EDF boost" not in score_breakdown(t)
