from django.db import models


class Doctor(models.Model):
    name = models.CharField(max_length=120)
    clinic = models.CharField(max_length=120)

    def __str__(self) -> str:
        return self.name


class WorkingHours(models.Model):
    """Weekly working hours — free slots are computed from these (FR-BOOK-001, task BOOK-001)."""

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField()  # 0 = Monday
    start = models.TimeField()
    end = models.TimeField()

    def __str__(self) -> str:
        return f"{self.doctor} · day {self.weekday} · {self.start:%H:%M}–{self.end:%H:%M}"
