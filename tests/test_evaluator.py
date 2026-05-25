"""
evaluator.py için birim testler
Çalıştır: pytest tests/test_evaluator.py -v
"""

import pytest
from datetime import datetime, timedelta

from core.task import Task
from core.scheduler import ScheduleResult, ScheduledTask
from core.evaluator import (
    Metrics, EvaluationReport,
    compute_metrics, evaluate, evaluate_all_scenarios,
)

NOW = datetime(2025, 1, 1, 9, 0)


# ──────────────────────────────────────────────
# Yardımcılar
# ──────────────────────────────────────────────

def _make_result(algorithm: str, importance_vals, urgency_vals, n_skipped=0) -> ScheduleResult:
    """Test için sentetik ScheduleResult üretir."""
    result = ScheduleResult(algorithm=algorithm)
    t = NOW
    for imp, urg in zip(importance_vals, urgency_vals):
        task = Task(name=f"T-{imp}", importance=imp, urgency=urg, duration=1.0)
        end  = t + timedelta(hours=1)
        result.scheduled.append(ScheduledTask(task=task, start_time=t, end_time=end, score=float(imp)))
        t = end
    for i in range(n_skipped):
        result.skipped.append(Task(name=f"Skip-{i}", importance=1, urgency=1, duration=1.0))
    return result


def _simple_tasks(n=5) -> list:
    return [
        Task(
            name=f"G{i}",
            importance=min(i + 1, 5),
            urgency=min(i + 1, 5),
            duration=1.0,
            created_at=NOW + timedelta(minutes=i),
        )
        for i in range(n)
    ]


# ──────────────────────────────────────────────
# 1. compute_metrics
# ──────────────────────────────────────────────

class TestComputeMetrics:

    def test_algorithm_label_preserved(self):
        result = _make_result("greedy_edf", [3, 4], [2, 3])
        m = compute_metrics(result)
        assert m.algorithm == "greedy_edf"

    def test_completed_count(self):
        result = _make_result("test", [1, 2, 3], [1, 2, 3])
        m = compute_metrics(result)
        assert m.completed_count == 3

    def test_skipped_count(self):
        result = _make_result("test", [1, 2], [1, 2], n_skipped=3)
        m = compute_metrics(result)
        assert m.skipped_count == 3

    def test_completed_importance_sum(self):
        result = _make_result("test", [2, 4, 5], [1, 1, 1])
        m = compute_metrics(result)
        assert m.completed_importance == 11

    def test_avg_urgency_correct(self):
        result = _make_result("test", [1, 1, 1], [2, 4, 3])
        m = compute_metrics(result)
        assert m.avg_urgency == pytest.approx(3.0)

    def test_avg_urgency_empty_schedule(self):
        result = ScheduleResult(algorithm="empty")
        m = compute_metrics(result)
        assert m.avg_urgency == 0.0

    def test_as_dict_keys(self):
        result = _make_result("test", [3], [3])
        d = compute_metrics(result).as_dict()
        for key in ("algorithm", "completed_count", "skipped_count",
                    "completed_importance", "missed_deadlines", "avg_urgency"):
            assert key in d


# ──────────────────────────────────────────────
# 2. EvaluationReport
# ──────────────────────────────────────────────

class TestEvaluationReport:

    def _report_with_three(self) -> EvaluationReport:
        report = EvaluationReport(scenario="test")
        report.metrics.append(Metrics("greedy_edf", 5, 2, 18, 0, 3.8))
        report.metrics.append(Metrics("random",     4, 3, 12, 2, 2.5))
        report.metrics.append(Metrics("fcfs",       4, 3, 14, 1, 3.0))
        return report

    def test_get_existing_algorithm(self):
        report = self._report_with_three()
        m = report.get("greedy_edf")
        assert m is not None
        assert m.algorithm == "greedy_edf"

    def test_get_missing_algorithm_returns_none(self):
        report = self._report_with_three()
        assert report.get("nonexistent") is None

    def test_algorithms_list(self):
        report = self._report_with_three()
        assert set(report.algorithms) == {"greedy_edf", "random", "fcfs"}

    def test_winner_importance_is_greedy(self):
        report = self._report_with_three()
        assert report.winner_importance() == "greedy_edf"

    def test_winner_deadlines_fewest_misses(self):
        report = self._report_with_three()
        assert report.winner_deadlines() == "greedy_edf"

    def test_winner_urgency_highest_avg(self):
        report = self._report_with_three()
        assert report.winner_urgency() == "greedy_edf"

    def test_print_table_runs_without_error(self, capsys):
        report = self._report_with_three()
        report.print_table()
        out = capsys.readouterr().out
        assert "TEST" in out
        assert "greedy_edf" in out.lower() or "GREEDY_EDF" in out


# ──────────────────────────────────────────────
# 3. evaluate()
# ──────────────────────────────────────────────

class TestEvaluate:

    def test_returns_three_metrics(self):
        tasks  = _simple_tasks(5)
        report = evaluate(tasks, scenario_name="test", start_time=NOW)
        assert len(report.metrics) == 3

    def test_scenario_name_set(self):
        tasks  = _simple_tasks(3)
        report = evaluate(tasks, scenario_name="deneme", start_time=NOW)
        assert report.scenario == "deneme"

    def test_all_three_algorithms_present(self):
        tasks  = _simple_tasks(4)
        report = evaluate(tasks, start_time=NOW)
        assert set(report.algorithms) == {"greedy_edf", "random", "fcfs"}

    def test_greedy_edf_importance_gte_random(self):
        """Yoğun senaryoda AI, random'dan düşük önem puanı almamalı."""
        from data.synthetic import scenario_yogun
        tasks  = scenario_yogun(now=NOW)
        report = evaluate(tasks, scenario_name="yogun",
                          available_hours=8.0, start_time=NOW)
        ai_imp  = report.get("greedy_edf").completed_importance
        rnd_imp = report.get("random").completed_importance
        assert ai_imp >= rnd_imp

    def test_empty_task_list(self):
        report = evaluate([], scenario_name="bos", start_time=NOW)
        for m in report.metrics:
            assert m.completed_count == 0
            assert m.skipped_count   == 0


# ──────────────────────────────────────────────
# 4. evaluate_all_scenarios()
# ──────────────────────────────────────────────

class TestEvaluateAllScenarios:

    def test_returns_three_scenarios(self):
        reports = evaluate_all_scenarios(start_time=NOW)
        assert set(reports.keys()) == {"rahat", "yogun", "imkansiz"}

    def test_each_report_has_three_metrics(self):
        reports = evaluate_all_scenarios(start_time=NOW)
        for report in reports.values():
            assert len(report.metrics) == 3

    def test_scenario_name_matches_key(self):
        reports = evaluate_all_scenarios(start_time=NOW)
        for name, report in reports.items():
            assert report.scenario == name

    def test_imkansiz_has_skipped_tasks(self):
        """İmkansız senaryoda her algoritmada atlanan görev olmalı."""
        reports = evaluate_all_scenarios(start_time=NOW)
        report  = reports["imkansiz"]
        for m in report.metrics:
            assert m.skipped_count > 0
