"""
Task veri modeli — Akıllı Görev Önceliklendirme Sistemi
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class Task:
    """
    Tek bir görevi temsil eder.

    Parametreler
    ------------
    name        : Görev adı
    importance  : Önem derecesi (1–5)
    urgency     : Aciliyet derecesi (1–5)
    duration    : Tahmini süre (saat, > 0)
    deadline    : Bitiş zamanı (opsiyonel, datetime)
    category    : Görev kategorisi (ör. "ders", "iş", "kişisel")
    created_at  : Oluşturulma zamanı (otomatik)
    """

    name: str
    importance: int
    urgency: int
    duration: float
    deadline: Optional[datetime] = None
    category: str = "genel"
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        errors = []

        if not self.name or not self.name.strip():
            errors.append("'name' boş olamaz.")
        if not (1 <= self.importance <= 5):
            errors.append(f"'importance' 1–5 arasında olmalı, alınan: {self.importance}")
        if not (1 <= self.urgency <= 5):
            errors.append(f"'urgency' 1–5 arasında olmalı, alınan: {self.urgency}")
        if self.duration <= 0:
            errors.append(f"'duration' sıfırdan büyük olmalı, alınan: {self.duration}")

        if errors:
            raise ValueError("Task doğrulama hatası:\n  - " + "\n  - ".join(errors))

        self.name = self.name.strip()
        self.category = (
            self.category.strip()
            .replace("İ", "i")
            .replace("I", "ı")
            .lower()
        )

    # ------------------------------------------------------------------
    # Yardımcı özellikler
    # ------------------------------------------------------------------

    @property
    def time_left(self) -> Optional[float]:
        """Deadline'a kalan süreyi saat cinsinden döndürür. Yoksa None."""
        if self.deadline is None:
            return None
        return (self.deadline - datetime.now()).total_seconds() / 3600

    @property
    def is_overdue(self) -> bool:
        tl = self.time_left
        return tl is not None and tl < 0

    @property
    def is_critical(self) -> bool:
        """EDF ön-filtresi: deadline'a ≤ 24 saat kalmış."""
        tl = self.time_left
        return tl is not None and 0 <= tl <= 24

    @property
    def deadline_pressure(self) -> float:
        """1 / (kalan_saat + 1). Deadline yoksa 0, geçmişse 1.0."""
        tl = self.time_left
        if tl is None:
            return 0.0
        if tl < 0:
            return 1.0
        return 1.0 / (tl + 1)

    # ------------------------------------------------------------------
    # Gösterim
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        dl = self.deadline.strftime("%d.%m %H:%M") if self.deadline else "—"
        return (
            f"Task({self.name!r}, imp={self.importance}, "
            f"urg={self.urgency}, dur={self.duration}h, dl={dl})"
        )

    def summary(self) -> str:
        tl = self.time_left
        tl_str = f"{tl:.1f}h" if tl is not None else "yok"
        flags = (" ⚠ KRİTİK" if self.is_critical else "") + \
                (" ✗ GECİKMİŞ" if self.is_overdue else "")
        return (
            f"{self.name:<28} "
            f"Önem:{self.importance}  Acil:{self.urgency}  "
            f"Süre:{self.duration}h  Kalan:{tl_str}{flags}"
        )


# ------------------------------------------------------------------
# Fabrika fonksiyonu
# ------------------------------------------------------------------

def make_task(
    name: str,
    importance: int,
    urgency: int,
    duration: float,
    deadline_hours: Optional[float] = None,
    **kwargs,
) -> Task:
    """deadline_hours ile kısa yoldan görev oluşturur."""
    deadline = (
        datetime.now() + timedelta(hours=deadline_hours)
        if deadline_hours is not None else None
    )
    return Task(name=name, importance=importance, urgency=urgency,
                duration=duration, deadline=deadline, **kwargs)
