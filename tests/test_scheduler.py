"""
scheduler.py ve synthetic.py için birim testler
Çalıştır: pytest tests/test_scheduler.py -v
"""

import pytest
from datetime import datetime, timedelta

from core.task import Task, make_task
from core.scheduler import (
    schedule, schedule_random, schedule_fcfs,
    ScheduleResult, ScheduledTask,
)
from data.synthetic import (
    sample_tasks, scenario_rahat, scenario_yogun,
    scenario_imkansiz, load_scenario,
)


# ──────────────────────────────────────────────
# Yardımcılar
# ──────────────────────────────────────────────

NOW = datetime(2025, 1, 1, 9, 0)  # sabit zaman → deterministik testler


def _tasks_fit(n=3, dur=1.0):
    """Toplam süresi available_hours'un altında basit görev seti."""
    return [
        Task(name=f"T{i}", importance=min(i+1, 5), urgency=min(i+1, 5), duration=dur,
             created_at=NOW + timedelta(minutes=i))
        for i in range(n)
    ]


# ──────────────────────────────────────────────
# 1. schedule() — temel davranış
# ──────────────────────────────────────────────

class TestSchedule:

    def test_all_tasks_scheduled_when_budget_sufficient(self):
        tasks = _tasks_fit(3, dur=1.0)   # 3h toplam, 8h bütçe
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        assert len(result.scheduled) == 3
        assert len(result.skipped) == 0

    def test_tasks_skipped_when_budget_insufficient(self):
        tasks = _tasks_fit(5, dur=2.0)   # 10h toplam, 8h bütçe
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        assert len(result.scheduled) + len(result.skipped) == 5
        assert len(result.skipped) >= 1

    def test_schedule_respects_time_budget(self):
        tasks = _tasks_fit(10, dur=1.0)
        result = schedule(tasks, available_hours=4.0, start_time=NOW)
        total = sum(s.task.duration for s in result.scheduled)
        assert total <= 4.0

    def test_end_time_equals_start_plus_duration(self):
        tasks = [Task(name="X", importance=3, urgency=3, duration=2.0,
                      created_at=NOW)]
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        s = result.scheduled[0]
        assert s.end_time == s.start_time + timedelta(hours=2.0)

    def test_consecutive_tasks_no_gap(self):
        """Ard arda gelen görevlerin arasında boşluk olmamalı."""
        tasks = _tasks_fit(3, dur=1.0)
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        for i in range(len(result.scheduled) - 1):
            assert result.scheduled[i].end_time == result.scheduled[i+1].start_time

    def test_deadline_violated_task_is_skipped(self):
        """Deadline'ı aşan görev planlanmamalı."""
        tight = Task(
            name="Sıkışık",
            importance=5, urgency=5, duration=3.0,
            deadline=NOW + timedelta(hours=1),  # 1h içinde bitmeli ama 3h sürüyor
            created_at=NOW,
        )
        result = schedule([tight], available_hours=8.0, start_time=NOW)
        assert len(result.skipped) == 1
        assert len(result.scheduled) == 0

    def test_algorithm_label(self):
        result = schedule([], available_hours=8.0, start_time=NOW)
        assert result.algorithm == "greedy_edf"

    def test_high_score_task_scheduled_before_low_score(self):
        """Yüksek skorlu görev düşük skorlu görevden önce planlanmalı."""
        low  = Task(name="Düşük",  importance=1, urgency=1, duration=1.0, created_at=NOW)
        high = Task(name="Yüksek", importance=5, urgency=5, duration=1.0, created_at=NOW)
        result = schedule([low, high], available_hours=8.0, start_time=NOW)
        assert result.scheduled[0].task.name == "Yüksek"


# ──────────────────────────────────────────────
# 2. ScheduleResult özellikleri
# ──────────────────────────────────────────────

class TestScheduleResult:

    def test_total_score_sum(self):
        tasks = _tasks_fit(3, dur=1.0)
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        expected = sum(s.score for s in result.scheduled)
        assert result.total_score == pytest.approx(expected)

    def test_completed_importance_sum(self):
        tasks = _tasks_fit(3, dur=1.0)
        result = schedule(tasks, available_hours=8.0, start_time=NOW)
        expected = sum(s.task.importance for s in result.scheduled)
        assert result.completed_importance == expected

    def test_summary_contains_algorithm(self):
        result = schedule([], available_hours=8.0, start_time=NOW)
        assert "greedy_edf" in result.summary()

    def test_empty_input(self):
        result = schedule([], available_hours=8.0, start_time=NOW)
        assert result.scheduled == []
        assert result.skipped == []
        assert result.total_score == 0.0


# ──────────────────────────────────────────────
# 3. Baseline algoritmaları
# ──────────────────────────────────────────────

class TestBaselines:

    def test_random_algorithm_label(self):
        result = schedule_random([], start_time=NOW)
        assert result.algorithm == "random"

    def test_fcfs_algorithm_label(self):
        result = schedule_fcfs([], start_time=NOW)
        assert result.algorithm == "fcfs"

    def test_fcfs_orders_by_created_at(self):
        """FCFS: önce oluşturulan görev önce planlanmalı."""
        t1 = Task(name="Önce",  importance=1, urgency=1, duration=1.0,
                  created_at=NOW)
        t2 = Task(name="Sonra", importance=5, urgency=5, duration=1.0,
                  created_at=NOW + timedelta(minutes=10))
        result = schedule_fcfs([t2, t1], available_hours=8.0, start_time=NOW)
        assert result.scheduled[0].task.name == "Önce"

    def test_random_same_seed_reproducible(self):
        tasks = _tasks_fit(5, dur=1.0)
        r1 = schedule_random(tasks, available_hours=8.0, start_time=NOW, seed=42)
        r2 = schedule_random(tasks, available_hours=8.0, start_time=NOW, seed=42)
        names1 = [s.task.name for s in r1.scheduled]
        names2 = [s.task.name for s in r2.scheduled]
        assert names1 == names2

    def test_ai_beats_random_on_importance_yogun(self):
        """
        Yoğun senaryoda AI, random'dan daha yüksek toplam önem puanı almalı.
        (seed=42 ile deterministik)
        """
        tasks = scenario_yogun(now=NOW)
        ai_result  = schedule(tasks,        available_hours=8.0, start_time=NOW)
        rnd_result = schedule_random(tasks, available_hours=8.0, start_time=NOW, seed=42)
        assert ai_result.completed_importance >= rnd_result.completed_importance


# ──────────────────────────────────────────────
# 4. Sentetik veri üreteci
# ──────────────────────────────────────────────

class TestSyntheticData:

    def test_sample_tasks_count(self):
        assert len(sample_tasks(now=NOW)) == 8

    def test_sample_tasks_valid(self):
        """Tüm örnek görevler geçerli Task nesnesi olmalı."""
        for t in sample_tasks(now=NOW):
            assert 1 <= t.importance <= 5
            assert 1 <= t.urgency <= 5
            assert t.duration > 0

    def test_scenario_rahat_reproducible(self):
        t1 = [t.name for t in scenario_rahat(now=NOW, seed=42)]
        t2 = [t.name for t in scenario_rahat(now=NOW, seed=42)]
        assert t1 == t2

    def test_scenario_yogun_has_more_tasks_than_rahat(self):
        assert len(scenario_yogun(now=NOW)) > len(scenario_rahat(now=NOW))

    def test_scenario_imkansiz_exceeds_budget(self):
        """İmkansız senaryonun toplam süresi 8 saati aşmalı."""
        tasks = scenario_imkansiz(now=NOW)
        total_dur = sum(t.duration for t in tasks)
        assert total_dur > 8.0

    def test_load_scenario_valid_names(self):
        for name in ("rahat", "yogun", "imkansiz"):
            tasks = load_scenario(name, now=NOW)
            assert len(tasks) > 0

    def test_load_scenario_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Bilinmeyen"):
            load_scenario("yanlış")
