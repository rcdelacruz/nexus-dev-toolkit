from django.db import models


class Reminder(models.Model):
    """A scheduled SMS reminder (FR-NOTIF-001). Scheduling and sending are task NOTIF-002."""

    appointment = models.OneToOneField(
        "booking.Appointment", on_delete=models.CASCADE, related_name="reminder"
    )
    send_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return f"reminder for {self.appointment_id} at {self.send_at:%Y-%m-%d %H:%M}"


class AccessLog(models.Model):
    """Every read of patient data (NFR-SEC-001) — writing it is task NOTIF-003."""

    user_id = models.BigIntegerField()
    patient_id = models.BigIntegerField()
    action = models.CharField(max_length=60)
    at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user_id} {self.action} patient {self.patient_id}"
