from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Atividade, Execucao


class ConcluirAtividadeTests(TestCase):
    """
    Cobre os critérios de aceite da tarefa TL-M1.
    """

    def setUp(self):
        self.prazo = timezone.now() + timedelta(days=2)

        self.atividade = Atividade.objects.create(
            usuario_id=1,
            titulo="Lista de exercícios 4",
            nome_disciplina="Cálculo 1",
            tipo="lista",
            prazo=self.prazo,
            duracao_estimada_min=90,
        )

    def url(self, atividade=None):
        return reverse(
            "concluir_atividade",
            args=[(atividade or self.atividade).id],
        )

    def test_post_conclui_a_atividade(self):
        self.client.post(self.url(), {"proximo": "hoje"})

        self.atividade.refresh_from_db()

        self.assertEqual(self.atividade.status, "concluida")

    def test_conclusao_registra_execucao(self):
        self.client.post(self.url(), {"proximo": "hoje"})

        execucao = Execucao.objects.get(atividade=self.atividade)

        self.assertEqual(execucao.tempo_previsto_min, 90)
        self.assertIsNotNone(execucao.concluido_em)

    def test_sem_duracao_estimada_assume_sessenta_minutos(self):
        atividade = Atividade.objects.create(
            usuario_id=1,
            titulo="Leitura do capítulo 7",
            tipo="leitura",
            prazo=self.prazo,
        )

        self.client.post(self.url(atividade), {"proximo": "hoje"})

        execucao = Execucao.objects.get(atividade=atividade)

        self.assertEqual(execucao.tempo_previsto_min, 60)

    def test_segundo_post_reabre_a_atividade(self):
        self.client.post(self.url(), {"proximo": "hoje"})
        self.client.post(self.url(), {"proximo": "hoje"})

        self.atividade.refresh_from_db()

        self.assertEqual(self.atividade.status, "planejada")

    def test_reabrir_remove_a_execucao(self):
        self.client.post(self.url(), {"proximo": "hoje"})
        self.client.post(self.url(), {"proximo": "hoje"})

        self.assertFalse(
            Execucao.objects.filter(atividade=self.atividade).exists()
        )

    def test_get_nao_altera_o_status(self):
        resposta = self.client.get(self.url())

        self.atividade.refresh_from_db()

        self.assertEqual(self.atividade.status, "planejada")
        self.assertEqual(resposta.status_code, 302)

    def test_atividade_de_outro_usuario_retorna_404(self):
        atividade = Atividade.objects.create(
            usuario_id=99,
            titulo="Atividade de outra pessoa",
            tipo="prova",
            prazo=self.prazo,
        )

        resposta = self.client.post(
            self.url(atividade),
            {"proximo": "hoje"},
        )

        atividade.refresh_from_db()

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(atividade.status, "planejada")

    def test_destino_externo_cai_na_pagina_hoje(self):
        resposta = self.client.post(
            self.url(),
            {"proximo": "https://exemplo.com/phishing"},
        )

        self.assertEqual(resposta["Location"], reverse("hoje"))

    def test_destino_permitido_e_respeitado(self):
        resposta = self.client.post(
            self.url(),
            {"proximo": "progresso"},
        )

        self.assertEqual(resposta["Location"], reverse("progresso"))


class ProgressoTests(TestCase):
    """
    Garante que a página de progresso reflete as conclusões reais.
    """

    def setUp(self):
        prazo = timezone.now() + timedelta(days=2)

        self.calculo = Atividade.objects.create(
            usuario_id=1,
            titulo="Relatório de laboratório",
            nome_disciplina="Cálculo 1",
            tipo="trabalho",
            prazo=prazo,
            duracao_estimada_min=120,
            status="concluida",
        )

        self.sem_disciplina = Atividade.objects.create(
            usuario_id=1,
            titulo="Leitura do capítulo 7",
            tipo="leitura",
            prazo=prazo,
            status="concluida",
        )

        self.pendente = Atividade.objects.create(
            usuario_id=1,
            titulo="Prova P2",
            nome_disciplina="Física 2",
            tipo="prova",
            prazo=prazo,
            duracao_estimada_min=180,
        )

    def test_percentual_usa_as_atividades_concluidas(self):
        resposta = self.client.get(reverse("progresso"))

        self.assertEqual(resposta.context["total"], 3)
        self.assertEqual(resposta.context["concluidas"], 2)
        self.assertEqual(resposta.context["percentual"], 67)

    def test_distribuicao_por_disciplina(self):
        resposta = self.client.get(reverse("progresso"))

        self.assertEqual(
            resposta.context["por_disciplina"],
            [
                {"disciplina": "Cálculo 1", "minutos": 120},
                {"disciplina": "Sem disciplina", "minutos": 60},
            ],
        )

    def test_atividade_pendente_fica_fora_da_distribuicao(self):
        disciplinas = [
            item["disciplina"]
            for item in self.client.get(
                reverse("progresso")
            ).context["por_disciplina"]
        ]

        self.assertNotIn("Física 2", disciplinas)

    def test_sem_atividades_nao_divide_por_zero(self):
        Atividade.objects.all().delete()

        resposta = self.client.get(reverse("progresso"))

        self.assertEqual(resposta.context["percentual"], 0)
        self.assertEqual(resposta.context["por_disciplina"], [])


class PlanejamentoIgnoraConcluidasTests(TestCase):
    """
    Atividade concluída não pode voltar a ser planejada.
    """

    def test_atividade_concluida_sai_do_ranking(self):
        prazo = timezone.now() + timedelta(days=2)

        Atividade.objects.create(
            usuario_id=1,
            titulo="Já entreguei",
            tipo="lista",
            prazo=prazo,
            status="concluida",
        )

        Atividade.objects.create(
            usuario_id=1,
            titulo="Ainda devo",
            tipo="lista",
            prazo=prazo,
        )

        resposta = self.client.get(reverse("planejamento"))

        titulos = [
            item["atividade"].titulo
            for item in resposta.context["prioridades"]
        ]

        self.assertEqual(titulos, ["Ainda devo"])
