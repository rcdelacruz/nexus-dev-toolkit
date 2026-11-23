from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("booking.urls")),
    path("accounts/", include("accounts.urls")),
    path("frontdesk/", include("frontdesk.urls")),
]
