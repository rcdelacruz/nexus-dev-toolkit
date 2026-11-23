from django.conf import settings
from django.db import models


class Appointment(models.Model):
    """One booked visit. The double-booking constraint (FR-BOOK-003) is task BOOK-004."""

    class Status(models.TextChoices):
        BOOKED = "booked"
        CANCELLED = "cancelled"

    doctor = models.ForeignKey("scheduling.Doctor", on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments"
    )
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)
    visit_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.doctor} · {self.starts_at:%Y-%m-%d %H:%M} · {self.status}"
