from django.urls import path

from . import views

app_name = "frontdesk"
urlpatterns = [path("schedule/", views.ClinicScheduleView.as_view(), name="schedule")]
