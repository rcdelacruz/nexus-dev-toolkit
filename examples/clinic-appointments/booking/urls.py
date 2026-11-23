from django.urls import path

from . import views

app_name = "booking"
urlpatterns = [
    path("", views.BookAppointmentView.as_view(), name="book"),
    path("my-appointments/", views.MyAppointmentsView.as_view(), name="my_appointments"),
]
