from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Atividade, InscricaoPush, LembreteEnviado
from core.management.commands.enviar_lembretes import Command


class LembretesPushTest(TestCase):

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario_teste",
            email="teste@example.com",
            password="senha123"
        )

        self.inscricao = InscricaoPush.objects.create(
            usuario=self.usuario,
            endpoint="https://fcm.googleapis.com/fcm/send/teste",
            p256dh="chave_teste",
            auth="auth_teste"
        )

    def criar_atividade(self, lembrete=0, minutos=0,
                        status="planejada", excluida=False):

        return Atividade.objects.create(
            usuario_id=self.usuario.id,
            titulo="Tarefa de teste",
            tipo="trabalho",
            prazo=timezone.now() + timedelta(minutes=minutos),
            lembrete_minutos=lembrete,
            status=status,
            excluido_em=timezone.now() if excluida else None
        )

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_lembrete_no_horario(self, mock_push):
        self.criar_atividade()

        Command().verificar_lembretes()

        mock_push.assert_called_once()
        self.assertEqual(LembreteEnviado.objects.count(), 1)

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_lembrete_antecipado(self, mock_push):
        self.criar_atividade(lembrete=30, minutos=30)

        Command().verificar_lembretes()

        mock_push.assert_called_once()

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_sem_lembrete(self, mock_push):
        self.criar_atividade(lembrete=None)

        Command().verificar_lembretes()

        mock_push.assert_not_called()

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_tarefa_concluida(self, mock_push):
        self.criar_atividade(status="concluida")

        Command().verificar_lembretes()

        mock_push.assert_not_called()

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_tarefa_excluida(self, mock_push):
        self.criar_atividade(excluida=True)

        Command().verificar_lembretes()

        mock_push.assert_not_called()

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_nao_duplicar_lembrete(self, mock_push):
        self.criar_atividade()

        Command().verificar_lembretes()
        Command().verificar_lembretes()

        mock_push.assert_called_once()
        self.assertEqual(LembreteEnviado.objects.count(), 1)

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_notificacoes_desativadas(self, mock_push):
        self.inscricao.delete()
        self.criar_atividade()

        Command().verificar_lembretes()

        mock_push.assert_not_called()

    @patch("core.management.commands.enviar_lembretes.webpush")
    def test_lembrete_futuro(self, mock_push):
        self.criar_atividade(lembrete=0, minutos=60)

        Command().verificar_lembretes()

        mock_push.assert_not_called()

class SegurancaPushTest(TestCase):

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuario1",
            email="usuario1@example.com",
            password="senha123"
        )

        self.outro_usuario = get_user_model().objects.create_user(
            username="usuario2",
            email="usuario2@example.com",
            password="senha123"
        )

        self.inscricao = InscricaoPush.objects.create(
            usuario=self.usuario,
            endpoint="https://fcm.googleapis.com/fcm/send/teste",
            p256dh="chave_teste",
            auth="auth_teste"
        )

    def test_logout_remove_inscricao(self):
        self.client.force_login(self.usuario)

        sessao = self.client.session
        sessao["push_endpoint"] = self.inscricao.endpoint
        sessao.save()

        self.client.post("/logout/")

        self.assertFalse(
            InscricaoPush.objects.filter(
                pk=self.inscricao.pk
            ).exists()
        )

    def test_inscricao_de_outra_conta(self):
        self.client.force_login(self.outro_usuario)

        resposta = self.client.post(
            "/push/status/",
            {"endpoint": self.inscricao.endpoint},
            content_type="application/json"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json()["ativo"])

    def test_nao_cancelar_inscricao_de_outra_conta(self):
        self.client.force_login(self.outro_usuario)

        self.client.post(
            "/push/cancelar/",
            {"endpoint": self.inscricao.endpoint},
            content_type="application/json"
        )

        self.assertTrue(
            InscricaoPush.objects.filter(
                pk=self.inscricao.pk
            ).exists()
        )