"""Celery app — reminders run here (ADR-CARESLOT-E003-001). Beat must run as one instance."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careslot.settings")

app = Celery("careslot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
