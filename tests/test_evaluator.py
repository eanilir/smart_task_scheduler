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

def test_imkansiz_has_skipped_tasks():
    """İmkansız senaryoda her algoritmada atlanan görev olmalı."""
    reports = evaluate_all_scenarios(start_time=NOW)
    report  = reports["imkansiz"]
    for m in report.metrics:
        assert m.skipped_count > 0