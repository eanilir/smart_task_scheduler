"""
Task dataclass için birim testler
Çalıştır: pytest tests/test_task.py -v
"""

import pytest
from datetime import datetime, timedelta
from core.task import Task, make_task


# ──────────────────────────────────────────────
# 1. Geçerli görev oluşturma
# ──────────────────────────────────────────────

class TestTaskCreation:

    def test_minimal_valid_task(self):
        t = Task(name="Ödev", importance=3, urgency=3, duration=2.0)
        assert t.name == "Ödev"
        assert t.importance == 3
        assert t.duration == 2.0
        assert t.deadline is None

    def test_full_valid_task(self):
        dl = datetime.now() + timedelta(hours=12)
        t = Task(
            name="Proje Raporu",
            importance=5,
            urgency=5,
            duration=3.0,
            deadline=dl,
            category="İŞ",
        )
        assert t.category == "iş"   # küçük harfe çevrilmeli
        assert t.deadline == dl

    def test_name_stripped(self):
        t = Task(name="  Boşluklu  ", importance=1, urgency=1, duration=1.0)
        assert t.name == "Boşluklu"

    def test_make_task_factory(self):
        t = make_task("Test", 3, 4, 1.5, deadline_hours=8)
        assert t.deadline is not None
        tl = t.time_left
        assert 7.9 < tl < 8.1


# ──────────────────────────────────────────────
# 2. Doğrulama hataları
# ──────────────────────────────────────────────

class TestValidation:

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            Task(name="", importance=3, urgency=3, duration=1.0)

    def test_whitespace_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            Task(name="   ", importance=3, urgency=3, duration=1.0)

    @pytest.mark.parametrize("val", [0, 6, -1])
    def test_importance_out_of_range(self, val):
        with pytest.raises(ValueError, match="importance"):
            Task(name="X", importance=val, urgency=3, duration=1.0)

    @pytest.mark.parametrize("val", [0, 6, -1])
    def test_urgency_out_of_range(self, val):
        with pytest.raises(ValueError, match="urgency"):
            Task(name="X", importance=3, urgency=val, duration=1.0)

    @pytest.mark.parametrize("val", [0.0, -1.0, -0.5])
    def test_duration_non_positive(self, val):
        with pytest.raises(ValueError, match="duration"):
            Task(name="X", importance=3, urgency=3, duration=val)

    def test_category_lowercased(self):
        t = Task(name="X", importance=3, urgency=3, duration=1.0, category="DERS")
        assert t.category == "ders"

    def test_multiple_errors_reported_together(self):
        with pytest.raises(ValueError) as exc_info:
            Task(name="", importance=0, urgency=6, duration=-1.0)
        msg = str(exc_info.value)
        assert "name" in msg
        assert "importance" in msg
        assert "urgency" in msg
        assert "duration" in msg


# ──────────────────────────────────────────────
# 3. Özellik hesaplamaları
# ──────────────────────────────────────────────

class TestProperties:

    def test_time_left_none_when_no_deadline(self):
        t = Task(name="X", importance=1, urgency=1, duration=1.0)
        assert t.time_left is None

    def test_time_left_positive_future(self):
        t = make_task("X", 1, 1, 1.0, deadline_hours=10)
        assert 9.9 < t.time_left < 10.1

    def test_is_overdue_past_deadline(self):
        t = Task(
            name="Geç Görev",
            importance=3, urgency=3, duration=1.0,
            deadline=datetime.now() - timedelta(hours=2),
        )
        assert t.is_overdue is True

    def test_is_not_overdue_future(self):
        t = make_task("X", 3, 3, 1.0, deadline_hours=5)
        assert t.is_overdue is False

    def test_is_critical_within_24h(self):
        t = make_task("Kritik", 4, 4, 2.0, deadline_hours=10)
        assert t.is_critical is True

    def test_is_not_critical_beyond_24h(self):
        t = make_task("Rahat", 2, 2, 1.0, deadline_hours=48)
        assert t.is_critical is False

    def test_deadline_pressure_no_deadline(self):
        t = Task(name="X", importance=1, urgency=1, duration=1.0)
        assert t.deadline_pressure == 0.0

    def test_deadline_pressure_increases_as_deadline_approaches(self):
        far  = make_task("Uzak",  1, 1, 1.0, deadline_hours=100)
        near = make_task("Yakın", 1, 1, 1.0, deadline_hours=2)
        assert near.deadline_pressure > far.deadline_pressure

    def test_deadline_pressure_overdue_is_max(self):
        t = Task(
            name="Gecikmiş",
            importance=3, urgency=3, duration=1.0,
            deadline=datetime.now() - timedelta(hours=1),
        )
        assert t.deadline_pressure == 1.0

    def test_summary_contains_name(self):
        t = make_task("Matematik Ödevi", 4, 3, 2.0, deadline_hours=20)
        assert "Matematik Ödevi" in t.summary()

    def test_repr_contains_key_fields(self):
        t = make_task("Test", 3, 4, 1.5)
        r = repr(t)
        assert "Test" in r
        assert "1.5" in r
