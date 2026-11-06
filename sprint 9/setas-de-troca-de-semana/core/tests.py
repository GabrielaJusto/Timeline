from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Compromisso


class AgendaSemanalTests(TestCase):
    """
    Cobre a navegação entre semanas da agenda.
    """

    def setUp(self):
        self.hoje = timezone.localdate()
        self.segunda = self.hoje - timedelta(days=self.hoje.weekday())

    def criar_compromisso(self, dia, titulo):
        inicio = timezone.make_aware(
            datetime.combine(dia, time(10, 0))
        )

        return Compromisso.objects.create(
            usuario_id=1,
            titulo=titulo,
            categoria="pessoal",
            inicio=inicio,
            fim=inicio + timedelta(hours=1),
        )

    def test_sem_parametro_mostra_a_semana_atual(self):
        resposta = self.client.get(reverse("agenda_semana"))

        self.assertEqual(
            resposta.context["inicio_semana"],
            self.segunda,
        )

    def test_parametro_semana_muda_a_semana_exibida(self):
        proxima = self.segunda + timedelta(days=7)

        resposta = self.client.get(
            reverse("agenda_semana"),
            {"semana": proxima.isoformat()},
        )

        self.assertEqual(
            resposta.context["inicio_semana"],
            proxima,
        )

    def test_data_no_meio_da_semana_cai_na_segunda(self):
        quarta = self.segunda + timedelta(days=9)

        resposta = self.client.get(
            reverse("agenda_semana"),
            {"semana": quarta.isoformat()},
        )

        self.assertEqual(
            resposta.context["inicio_semana"],
            self.segunda + timedelta(days=7),
        )

    def test_setas_apontam_para_a_semana_vizinha(self):
        resposta = self.client.get(reverse("agenda_semana"))

        self.assertEqual(
            resposta.context["semana_anterior"],
            self.segunda - timedelta(days=7),
        )
        self.assertEqual(
            resposta.context["semana_seguinte"],
            self.segunda + timedelta(days=7),
        )

    def test_compromisso_aparece_na_semana_certa(self):
        proxima_quarta = self.segunda + timedelta(days=9)

        self.criar_compromisso(proxima_quarta, "Reunião do projeto")

        atual = self.client.get(reverse("agenda_semana"))
        seguinte = self.client.get(
            reverse("agenda_semana"),
            {"semana": proxima_quarta.isoformat()},
        )

        def titulos(resposta):
            return [
                compromisso.titulo
                for dia in resposta.context["dias"]
                for compromisso in dia["compromissos"]
            ]

        self.assertNotIn("Reunião do projeto", titulos(atual))
        self.assertIn("Reunião do projeto", titulos(seguinte))

    def test_semana_invalida_cai_na_semana_atual(self):
        for valor in ["lixo", "", "2026-13-45", "01/02/2026"]:
            with self.subTest(valor=valor):
                resposta = self.client.get(
                    reverse("agenda_semana"),
                    {"semana": valor},
                )

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(
                    resposta.context["inicio_semana"],
                    self.segunda,
                )

    def test_marca_quando_a_semana_exibida_e_a_atual(self):
        atual = self.client.get(reverse("agenda_semana"))

        outra = self.client.get(
            reverse("agenda_semana"),
            {"semana": (self.segunda + timedelta(days=7)).isoformat()},
        )

        self.assertTrue(atual.context["semana_atual"])
        self.assertFalse(outra.context["semana_atual"])

    def test_data_atual_continua_sendo_hoje(self):
        """
        O destaque do dia corrente não pode seguir a semana navegada.
        """

        resposta = self.client.get(
            reverse("agenda_semana"),
            {"semana": (self.segunda + timedelta(days=70)).isoformat()},
        )

        self.assertEqual(resposta.context["data_atual"], self.hoje)

    def test_titulo_da_semana_e_preenchido(self):
        resposta = self.client.get(reverse("agenda_semana"))

        self.assertTrue(resposta.context["titulo_semana"].strip())
