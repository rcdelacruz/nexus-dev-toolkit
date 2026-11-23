from django.views.generic import TemplateView


class ClinicScheduleView(TemplateView):
    """DES-002 Clinic Schedule — shell only; the schedule grid is task SCHED-001."""

    template_name = "frontdesk/clinic_schedule.html"
