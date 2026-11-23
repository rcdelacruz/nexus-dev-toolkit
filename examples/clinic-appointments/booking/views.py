from django.views.generic import TemplateView


class BookAppointmentView(TemplateView):
    """DES-001 Book Appointment — shell only; slots are task BOOK-001/002, booking BOOK-003."""

    template_name = "booking/book_appointment.html"


class MyAppointmentsView(TemplateView):
    """DES-003 My Appointments — shell only; listing and cancelling are task BOOK-005/006."""

    template_name = "booking/my_appointments.html"
