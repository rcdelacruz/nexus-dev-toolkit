from django.views.generic import TemplateView


class SignInView(TemplateView):
    """DES-004 Sign In — shell only; authentication is task SCHED-003."""

    template_name = "accounts/sign_in.html"
