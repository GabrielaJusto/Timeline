from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Atividade


class BaseTelaHoje(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        self.usuario = Usuario.objects.create_user(
            username="estudante",
            password="senha-de-teste-123",
        )

        self.client.force_login(self.usuario)

        self.hoje = timezone.localdate()
        self.segunda = self.hoje - timedelta(days=self.hoje.weekday())

    def criar(self, titulo, dias, **extra):
        return Atividade.objects.create(
            usuario_id=extra.pop("usuario_id", self.usuario.id),
            titulo=titulo,
            tipo=extra.pop("tipo", "lista"),
            prazo=timezone.now() + timedelta(days=dias),
            **extra,
        )

    def no_dia(self, titulo, dia, hora=time(10, 0), **extra):
        return Atividade.objects.create(
            usuario_id=self.usuario.id,
            titulo=titulo,
            tipo="lista",
            prazo=timezone.make_aware(datetime.combine(dia, hora)),
            **extra,
        )


class ProximoPrazoTests(BaseTelaHoje):
    """
    O painel "Próximo prazo" era texto fixo: dizia que os prazos
    apareceriam ali depois de cadastrar uma tarefa, mesmo com
    tarefas cadastradas.
    """

    def test_sem_tarefas_nao_ha_proxima(self):
        resposta = self.client.get(reverse("hoje"))

        self.assertIsNone(resposta.context["proxima"])
        self.assertContains(resposta, "O próximo passo")

    def test_mostra_a_tarefa_de_prazo_mais_perto(self):
        self.criar("Daqui a seis dias", 6)
        self.criar("Daqui a dois dias", 2)
        self.criar("Daqui a dez dias", 10)

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(
            resposta.context["proxima"].titulo,
            "Daqui a dois dias",
        )
        self.assertContains(resposta, "Daqui a dois dias")

    def test_tarefa_concluida_nao_vira_proximo_prazo(self):
        self.criar("Já entreguei", 1, status="concluida")
        self.criar("Ainda devo", 5)

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(
            resposta.context["proxima"].titulo,
            "Ainda devo",
        )

    def test_tarefa_vencida_continua_sendo_o_proximo_passo(self):
        self.criar("Venceu ontem", -1)
        self.criar("Vence amanha", 1)

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(
            resposta.context["proxima"].titulo,
            "Venceu ontem",
        )
        self.assertEqual(resposta.context["dias_para_o_prazo"], -1)
        self.assertContains(resposta, "Venceu em")

    def test_prazo_de_hoje_aparece_como_hoje(self):
        self.no_dia("Entrega de hoje", self.hoje, time(23, 0))

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["dias_para_o_prazo"], 0)
        self.assertContains(resposta, "É hoje")

    def test_prazo_de_amanha_aparece_como_amanha(self):
        self.no_dia("Entrega de amanha", self.hoje + timedelta(days=1))

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["dias_para_o_prazo"], 1)
        self.assertContains(resposta, "Amanhã")

    def test_tarefa_de_outro_usuario_nao_aparece(self):
        self.criar("Da outra pessoa", 1, usuario_id=9999)

        resposta = self.client.get(reverse("hoje"))

        self.assertIsNone(resposta.context["proxima"])

    def test_botao_comecar_vira_link(self):
        self.criar("Uma tarefa", 2)

        resposta = self.client.get(reverse("hoje"))

        self.assertContains(
            resposta,
            f'href="{reverse("tarefas")}" class="botao-comecar"',
        )


class ProgressoDaSemanaTests(BaseTelaHoje):
    """
    O contador da semana estava escrito no HTML como
    "0 de 0 tarefas concluídas" e "0%".
    """

    def test_sem_tarefas_fica_em_zero_sem_dividir_por_zero(self):
        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["total_semana"], 0)
        self.assertEqual(resposta.context["percentual_semana"], 0)

    def test_conta_as_tarefas_da_semana(self):
        self.no_dia("Segunda", self.segunda)
        self.no_dia("Quarta", self.segunda + timedelta(days=2))
        self.no_dia("Domingo", self.segunda + timedelta(days=6))

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["total_semana"], 3)

    def test_tarefa_de_outra_semana_fica_de_fora(self):
        self.no_dia("Semana que vem", self.segunda + timedelta(days=7))
        self.no_dia("Semana passada", self.segunda - timedelta(days=1))
        self.no_dia("Desta semana", self.segunda + timedelta(days=1))

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["total_semana"], 1)

    def test_percentual_usa_as_concluidas(self):
        self.no_dia("Feita", self.segunda, status="concluida")
        self.no_dia("Feita tambem", self.segunda, status="concluida")
        self.no_dia("Pendente", self.segunda + timedelta(days=1))
        self.no_dia("Pendente tambem", self.segunda + timedelta(days=2))

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["concluidas_semana"], 2)
        self.assertEqual(resposta.context["total_semana"], 4)
        self.assertEqual(resposta.context["percentual_semana"], 50)
        self.assertContains(resposta, "50%")

    def test_nao_sobrou_zero_de_zero_no_html(self):
        self.no_dia("Desta semana", self.segunda + timedelta(days=1))

        resposta = self.client.get(reverse("hoje"))

        self.assertNotContains(resposta, "0 de 0 tarefas concluídas")
