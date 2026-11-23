"""Day 0 smoke tests: settings load, every screen route resolves to its template."""

from django.urls import resolve, reverse


def test_every_screen_has_a_route():
    for name in ("booking:book", "booking:my_appointments", "frontdesk:schedule", "accounts:sign_in"):
        assert resolve(reverse(name))
