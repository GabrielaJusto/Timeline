from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST


class RecuperarSenhaView(auth_views.PasswordResetView):
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.txt"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        if settings.EMAIL_BACKEND in {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        }:
            form.add_error(None, "A recuperação de senha está temporariamente indisponível. Tente novamente mais tarde.")
            return self.form_invalid(form)
        try:
            return super().form_valid(form)
        except (OSError, SMTPException):
            form.add_error(None, "Não foi possível enviar o e-mail agora. Tente novamente mais tarde.")
            return self.form_invalid(form)


@require_POST
def google_login(request):
    if not settings.GOOGLE_LOGIN_ENABLED:
        return render(request, "auth/google_unavailable.html")
    from allauth.socialaccount.providers.google.views import oauth2_login

    return oauth2_login(request)
