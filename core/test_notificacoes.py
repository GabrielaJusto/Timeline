from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AlertaCarga, Atividade, Planejamento


class BaseNotificacoes(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        self.usuario = Usuario.objects.create_user(
            username="estudante",
            password="senha-de-teste-123",
        )

        self.client.force_login(self.usuario)

    def criar_atividade(self, titulo, dias, **extra):
        """
        Dias negativos produzem uma atividade atrasada.
        """

        return Atividade.objects.create(
            usuario_id=extra.pop("usuario_id", self.usuario.id),
            titulo=titulo,
            tipo=extra.pop("tipo", "lista"),
            prazo=timezone.now() + timedelta(days=dias),
            **extra,
        )


class NotificacoesTests(BaseNotificacoes):
    """
    A view de notificações renderizava o template sem contexto nenhum,
    então a página dizia "Tudo em dia" mesmo com atividade vencida.
    """

    def test_exige_login(self):
        self.client.logout()

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta["Location"])

    def test_atividade_vencida_entra_em_atrasadas(self):
        self.criar_atividade("Entrega de ontem", -1)

        resposta = self.client.get(reverse("notificacoes"))

        titulos = [a.titulo for a in resposta.context["atrasadas"]]

        self.assertEqual(titulos, ["Entrega de ontem"])
        self.assertContains(resposta, "Atividade atrasada")

    def test_nao_diz_tudo_em_dia_com_atrasada(self):
        self.criar_atividade("Entrega de ontem", -1)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertNotContains(resposta, "Tudo em dia")

    def test_atividade_proxima_entra_na_lista_da_semana(self):
        self.criar_atividade("Lista de cálculo", 3)

        resposta = self.client.get(reverse("notificacoes"))

        titulos = [a.titulo for a in resposta.context["atividades"]]

        self.assertEqual(titulos, ["Lista de cálculo"])
        self.assertEqual(resposta.context["total_semana"], 1)

    def test_atividade_distante_fica_de_fora(self):
        self.criar_atividade("Prova do mês que vem", 30)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 0)

    def test_atividade_concluida_nao_gera_aviso(self):
        self.criar_atividade("Já entreguei", -2, status="concluida")

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(len(resposta.context["atrasadas"]), 0)
        self.assertEqual(resposta.context["total_semana"], 0)

    def test_atividade_na_lixeira_nao_gera_aviso(self):
        atividade = self.criar_atividade("Mandei para a lixeira", -1)
        atividade.excluido_em = timezone.now()
        atividade.save(update_fields=["excluido_em"])

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(len(resposta.context["atrasadas"]), 0)

    def test_atividade_de_outro_usuario_nao_aparece(self):
        self.criar_atividade("Da outra pessoa", 2, usuario_id=9999)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 0)

    def test_sem_pendencias_diz_tudo_em_dia(self):
        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_avisos"], 0)
        self.assertContains(resposta, "Tudo em dia")

    def test_aviso_de_semana_cheia_a_partir_de_tres(self):
        for i in range(3):
            self.criar_atividade(f"Atividade {i}", i + 1)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 3)
        self.assertContains(resposta, "Semana com muitas atividades")

    def test_ordena_da_mais_urgente_para_a_menos(self):
        self.criar_atividade("Daqui a seis dias", 6)
        self.criar_atividade("Amanhã", 1)
        self.criar_atividade("Daqui a tres dias", 3)

        resposta = self.client.get(reverse("notificacoes"))

        titulos = [a.titulo for a in resposta.context["atividades"]]

        self.assertEqual(
            titulos,
            ["Amanhã", "Daqui a tres dias", "Daqui a seis dias"],
        )


class AlertaDeCargaTests(BaseNotificacoes):
    """
    O modelo AlertaCarga existe no projeto e nunca era populado.
    """

    def criar_planejamento(self, disponiveis, alocadas):
        hoje_local = timezone.localdate()
        segunda = hoje_local - timedelta(days=hoje_local.weekday())

        return Planejamento.objects.create(
            usuario_id=self.usuario.id,
            semana_inicio=segunda,
            semana_fim=segunda + timedelta(days=6),
            status="ativo",
            horas_disponiveis=disponiveis,
            horas_alocadas=alocadas,
        )

    def test_carga_tranquila_nao_gera_alerta(self):
        self.criar_planejamento(20, 10)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(len(resposta.context["alertas"]), 0)

    def test_carga_alta_gera_alerta(self):
        self.criar_planejamento(20, 17)

        resposta = self.client.get(reverse("notificacoes"))

        alertas = resposta.context["alertas"]

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].nivel, "Carga alta")

    def test_carga_critica_gera_alerta(self):
        self.criar_planejamento(10, 12)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(
            resposta.context["alertas"][0].nivel,
            "Carga crítica",
        )

    def test_alerta_nao_duplica_a_cada_visita(self):
        self.criar_planejamento(10, 12)

        for _ in range(3):
            self.client.get(reverse("notificacoes"))

        self.assertEqual(AlertaCarga.objects.count(), 1)

    def test_alerta_some_quando_a_carga_normaliza(self):
        planejamento = self.criar_planejamento(10, 12)

        self.client.get(reverse("notificacoes"))
        self.assertEqual(AlertaCarga.objects.count(), 1)

        planejamento.horas_alocadas = 4
        planejamento.save()

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(AlertaCarga.objects.count(), 0)
        self.assertEqual(len(resposta.context["alertas"]), 0)

    def test_sem_horas_disponiveis_nao_divide_por_zero(self):
        self.criar_planejamento(0, 5)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context["alertas"]), 0)
