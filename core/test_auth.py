from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="aluna", email="aluna@example.com", password="SenhaOriginal!5427"
        )

    def reset_url(self):
        return reverse("password_reset_confirm", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": default_token_generator.make_token(self.user),
        })

    def test_password_login_still_works(self):
        response = self.client.post(reverse("login"), {
            "username": "aluna", "password": "SenhaOriginal!5427",
        })
        self.assertRedirects(response, reverse("hoje"))

    def test_reset_sends_one_time_link_and_does_not_disclose_unknown_email(self):
        response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/senha/redefinir/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        unknown = self.client.post(reverse("password_reset"), {"email": "unknown@example.com"})
        self.assertEqual(response.url, unknown.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_changes_password_and_rejects_reuse(self):
        url = self.reset_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        result = self.client.post(response.url, {
            "new_password1": "SenhaNova!73625", "new_password2": "SenhaNova!73625",
        })
        self.assertRedirects(result, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("SenhaNova!73625"))
        self.assertFalse(self.user.check_password("SenhaOriginal!5427"))
        reused = self.client.get(url)
        self.assertFalse(reused.context["validlink"])

    def test_expired_link_cannot_change_password(self):
        now = default_token_generator._now()
        with patch.object(default_token_generator, "_now", return_value=now - timedelta(hours=2)):
            url = self.reset_url()
        response = self.client.get(url)
        self.assertFalse(response.context["validlink"])

    def test_password_mismatch_preserves_form(self):
        response = self.client.get(self.reset_url())
        response = self.client.post(response.url, {
            "new_password1": "SenhaNova!73625", "new_password2": "OutraSenha!6364",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    def test_email_failure_shows_error_instead_of_blank_screen(self):
        with patch("django.contrib.auth.forms.PasswordResetForm.send_mail", side_effect=SMTPException):
            response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_reset_does_not_claim_email_sent_when_delivery_is_not_configured(self):
        with patch("django.contrib.auth.forms.PasswordResetForm.send_mail") as send_mail:
            for email in (self.user.email, "unknown@example.com"):
                response = self.client.post(reverse("password_reset"), {"email": email})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "temporariamente indisponível")
                self.assertTrue(response.context["form"].non_field_errors())
            send_mail.assert_not_called()

    def test_duplicate_username_displays_highlighted_error(self):
        response = self.client.post(reverse("cadastro"), {
            "username": "aluna", "email": "nova@example.com",
            "nome_completo": "Maria Silva", "faculdade": "Universidade Teste",
            "data_nascimento": "2001-04-20",
            "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
        })
        self.assertIn("username", response.context["formulario"].errors)
        self.assertContains(response, 'class="campo campo--erro"')
        self.assertContains(response, 'class="field-error" id="id_username_error" role="alert"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, "Confira os campos destacados")

    def test_signup_requires_email_and_preserves_normal_login(self):
        data = {
            "username": "nova", "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
            "nome_completo": "Ana Maria Silva", "faculdade": "PUC-Rio", "data_nascimento": "2000-05-20",
        }
        response = self.client.post(reverse("cadastro"), data)
        self.assertIn("email", response.context["formulario"].errors)
        response = self.client.post(reverse("cadastro"), {**data, "email": "nova@example.com"})
        self.assertRedirects(response, reverse("hoje"))
        user = get_user_model().objects.get(username="nova")
        self.assertEqual(user.email, "nova@example.com")
        self.assertEqual(user.get_full_name(), "Ana Maria Silva")
        self.assertEqual(user.perfil_aluno.nome_completo, "Ana Maria Silva")
        self.assertEqual(user.perfil_aluno.faculdade, "PUC-Rio")
        self.assertEqual(user.perfil_aluno.data_nascimento.isoformat(), "2000-05-20")

    def test_signup_rejects_duplicate_email(self):
        response = self.client.post(reverse("cadastro"), {
            "username": "outra", "email": "ALUNA@example.com",
            "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
        })
        self.assertIn("email", response.context["formulario"].errors)

    def test_signup_rejects_future_birthday_without_creating_account(self):
        from django.utils import timezone

        response = self.client.post(reverse("cadastro"), {
            "username": "futura", "email": "futura@example.com",
            "nome_completo": "Maria Silva", "faculdade": "Universidade Teste",
            "data_nascimento": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
        })
        self.assertIn("data_nascimento", response.context["formulario"].errors)
        self.assertEqual(response.context["formulario"]["nome_completo"].value(), "Maria Silva")
        self.assertFalse(get_user_model().objects.filter(username="futura").exists())

    def test_signup_requires_student_information(self):
        response = self.client.post(reverse("cadastro"), {
            "username": "incompleta", "email": "incompleta@example.com",
            "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
        })
        for field in ("nome_completo", "faculdade", "data_nascimento"):
            self.assertIn(field, response.context["formulario"].errors)
        self.assertFalse(get_user_model().objects.filter(username="incompleta").exists())

    def test_new_student_can_request_reset_using_registered_email(self):
        self.client.post(reverse("cadastro"), {
            "username": "estudante", "email": "estudante@example.com",
            "nome_completo": "Maria Silva", "faculdade": "Universidade Teste",
            "data_nascimento": "2001-04-20",
            "password1": "CadastroNovo!5427", "password2": "CadastroNovo!5427",
        })
        self.client.logout()
        response = self.client.post(reverse("password_reset"), {"email": "estudante@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["estudante@example.com"])

    @override_settings(GOOGLE_LOGIN_ENABLED=False)
    def test_google_missing_configuration_has_helpful_screen(self):
        self.assertEqual(self.client.get(reverse("login_google")).status_code, 405)
        response = self.client.post(reverse("login_google"))
        self.assertContains(response, "ainda não foi ativada")

    @override_settings(GOOGLE_LOGIN_ENABLED=True, SOCIALACCOUNT_PROVIDERS={"google": {
        "APP": {"client_id": "test.apps.googleusercontent.com", "secret": "test-secret", "key": ""},
        "SCOPE": ["profile", "email"], "OAUTH_PKCE_ENABLED": True,
    }})
    def test_google_redirect_uses_state_and_pkce_and_no_client_secret(self):
        response = self.client.post(reverse("login_google"))
        self.assertEqual(response.status_code, 302)
        url = urlparse(response.url)
        self.assertEqual(url.netloc, "accounts.google.com")
        query = parse_qs(url.query)
        self.assertIn("state", query)
        self.assertIn("code_challenge", query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["redirect_uri"][0].endswith("/accounts/google/login/callback/"))
        self.assertNotIn("test-secret", response.url)

    def test_oauth_callback_without_state_does_not_log_in(self):
        response = self.client.get("/accounts/google/login/callback/?code=invalid&state=invalid")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(GOOGLE_LOGIN_ENABLED=True, SOCIALACCOUNT_PROVIDERS={"google": {
        "APP": {"client_id": "test.apps.googleusercontent.com", "secret": "test-secret", "key": ""},
        "SCOPE": ["profile", "email"], "OAUTH_PKCE_ENABLED": True,
    }})
    def test_google_callback_creates_account_and_next_login_reuses_it(self):
        from allauth.socialaccount.models import SocialAccount

        for attempt in range(2):
            self.client.logout()
            start = self.client.post(reverse("login_google"))
            state = parse_qs(urlparse(start.url).query)["state"][0]
            with patch(
                "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.get_access_token_data",
                return_value={"access_token": "test-token", "token_type": "Bearer"},
            ), patch(
                "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter._fetch_user_info",
                return_value={"id": "google-123", "email": "google@example.com", "verified_email": True, "name": "Aluna Google"},
            ):
                response = self.client.get("/accounts/google/login/callback/", {"code": "test-code", "state": state})
            self.assertRedirects(response, reverse("hoje"))
            self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(SocialAccount.objects.filter(provider="google", uid="google-123").count(), 1)
        self.assertEqual(get_user_model().objects.filter(email="google@example.com").count(), 1)

    def test_reset_and_google_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("password_reset"), {"email": self.user.email}).status_code, 403)
        self.assertEqual(client.post(reverse("login_google")).status_code, 403)
