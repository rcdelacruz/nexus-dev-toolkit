from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Patients, receptionists and doctors (US-001). Lockout after failed sign-ins is task SCHED-003."""

    class Role(models.TextChoices):
        PATIENT = "patient"
        RECEPTIONIST = "receptionist"
        DOCTOR = "doctor"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=30, blank=True)  # SMS reminders (FR-NOTIF-001)
