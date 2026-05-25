"""
Sentetik Veri Üreteci — Akıllı Görev Önceliklendirme Sistemi

Üç senaryo üretir:
    rahat   → görevler sığar, deadline baskısı az
    yogun   → görevler zar zor sığar, çakışmalar var
    imkansiz→ toplam süre available_hours'u aşar

Her senaryo random.seed(42) ile sabitlenmiştir → tekrar üretilebilir.
"""

from __future__ import annotations
import random
from datetime import datetime, timedelta
from typing import List

from core.task import Task


# ──────────────────────────────────────────────────────────────────────
# Sabit örnek görevler (proje raporunda kullanılacak)
# ──────────────────────────────────────────────────────────────────────

def sample_tasks(now: datetime | None = None) -> List[Task]:
    """
    Projede tanımlanan örnek görev seti.
    Deadline'lar now anından itibaren hesaplanır.
    """
    if now is None:
        now = datetime.now()

    return [
        Task("Proje Raporu",  importance=5, urgency=5, duration=3.0,
             deadline=now + timedelta(hours=5),  category="iş"),
        Task("Matematik Ödevi", importance=4, urgency=3, duration=2.0,
             deadline=now + timedelta(hours=7),  category="ders"),
        Task("Video İzle",    importance=1, urgency=1, duration=1.0,
             category="kişisel"),
        Task("E-posta Yanıtla", importance=3, urgency=4, duration=0.5,
             deadline=now + timedelta(hours=3),  category="iş"),
        Task("Kitap Oku",     importance=2, urgency=2, duration=1.5,
             category="kişisel"),
        Task("Sunum Hazırla", importance=5, urgency=4, duration=4.0,
             deadline=now + timedelta(hours=10), category="iş"),
        Task("Alışveriş",    importance=2, urgency=3, duration=1.0,
             deadline=now + timedelta(hours=6),  category="kişisel"),
        Task("Kod Review",   importance=4, urgency=4, duration=2.0,
             deadline=now + timedelta(hours=8),  category="iş"),
    ]


# ──────────────────────────────────────────────────────────────────────
# Rastgele senaryo üreteci
# ──────────────────────────────────────────────────────────────────────

def _make_tasks(
    n: int,
    imp_range: tuple,
    urg_range: tuple,
    dur_range: tuple,
    deadline_ratio: float,
    deadline_hours_range: tuple,
    rng: random.Random,
    now: datetime,
) -> List[Task]:
    """İç yardımcı: parametrelerle n adet görev üretir."""
    categories = ["ders", "iş", "kişisel", "genel"]
    tasks = []
    for i in range(n):
        imp = rng.randint(*imp_range)
        urg = rng.randint(*urg_range)
        dur = round(rng.uniform(*dur_range), 1)

        deadline = None
        if rng.random() < deadline_ratio:
            dh = rng.uniform(*deadline_hours_range)
            deadline = now + timedelta(hours=dh)

        # created_at'ı biraz dağıt → FCFS baseline anlamlı olsun
        created = now - timedelta(minutes=rng.randint(0, 120))

        tasks.append(Task(
            name=f"Görev-{i+1:02d}",
            importance=imp,
            urgency=urg,
            duration=dur,
            deadline=deadline,
            category=rng.choice(categories),
            created_at=created,
        ))
    return tasks


def scenario_rahat(now: datetime | None = None, seed: int = 42) -> List[Task]:
    """
    Rahat senaryo — 6 görev, toplam süre ~6h, available_hours=8.
    Tüm görevler sığabilir; deadline baskısı düşük.
    Beklenti: AI ve FCFS benzer sonuç, random daha kötü.
    """
    if now is None:
        now = datetime.now()
    rng = random.Random(seed)
    return _make_tasks(
        n=6,
        imp_range=(1, 5), urg_range=(1, 5),
        dur_range=(0.5, 1.5),
        deadline_ratio=0.4,
        deadline_hours_range=(6, 12),
        rng=rng, now=now,
    )


def scenario_yogun(now: datetime | None = None, seed: int = 42) -> List[Task]:
    """
    Yoğun senaryo — 12 görev, toplam süre ~10–12h, available_hours=8.
    Bazı görevler atlanmak zorunda; sıralama kritik önem taşır.
    Beklenti: AI > FCFS > Random (deadline kaçırma sayısında net fark)
    """
    if now is None:
        now = datetime.now()
    rng = random.Random(seed)
    return _make_tasks(
        n=12,
        imp_range=(1, 5), urg_range=(1, 5),
        dur_range=(0.5, 2.0),
        deadline_ratio=0.7,
        deadline_hours_range=(2, 9),
        rng=rng, now=now,
    )


def scenario_imkansiz(now: datetime | None = None, seed: int = 42) -> List[Task]:
    """
    İmkansız senaryo — 10 görev, her biri 1.5–3h, available_hours=8.
    Toplam süre available_hours'un çok üstünde; çoğu görev atlanır.
    Beklenti: AI en yüksek önem puanlı görevleri seçer.
    """
    if now is None:
        now = datetime.now()
    rng = random.Random(seed)
    return _make_tasks(
        n=10,
        imp_range=(1, 5), urg_range=(1, 5),
        dur_range=(1.5, 3.0),
        deadline_ratio=0.8,
        deadline_hours_range=(1, 6),
        rng=rng, now=now,
    )


# ──────────────────────────────────────────────────────────────────────
# Toplu erişim
# ──────────────────────────────────────────────────────────────────────

ALL_SCENARIOS = {
    "rahat":     scenario_rahat,
    "yogun":     scenario_yogun,
    "imkansiz":  scenario_imkansiz,
}


def load_scenario(name: str, now: datetime | None = None) -> List[Task]:
    """
    İsme göre senaryo yükler.

    Kullanım:
        tasks = load_scenario("yogun")
    """
    if name not in ALL_SCENARIOS:
        raise ValueError(f"Bilinmeyen senaryo: {name!r}. Geçerliler: {list(ALL_SCENARIOS)}")
    return ALL_SCENARIOS[name](now=now)
