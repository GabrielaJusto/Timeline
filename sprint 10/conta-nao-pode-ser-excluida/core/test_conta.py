import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Atividade,
    Compromisso,
    PerfilAluno,
    Planejamento,
    SessaoPlanejada,
    Subtarefa,
)


class DadosDaContaMixin:
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.ana = U.objects.create_user(username="ana", email="ana@exemplo.test", password="senha-segura-123")
        PerfilAluno.objects.create(usuario=cls.ana, nome_completo="Ana Silva", faculdade="PUC-Rio", data_nascimento=date(2003, 4, 10))
        cls.bia = U.objects.create_user(username="bia", password="outra-senha-123")
        cls.criar_dados(cls.ana, "Ana")
        cls.criar_dados(cls.bia, "Bia")

    @staticmethod
    def criar_dados(usuario, nome):
        agora = timezone.now()
        tarefa = Atividade.objects.create(usuario_id=usuario.id, titulo=f"Lista de {nome}", tipo="lista", prazo=agora + timedelta(days=2))
        Subtarefa.objects.create(atividade=tarefa, titulo="Questão 1")
        Atividade.objects.create(usuario_id=usuario.id, titulo=f"Tarefa na lixeira de {nome}", tipo="outro", prazo=agora, excluido_em=agora)
        Compromisso.objects.create(usuario_id=usuario.id, titulo=f"Reunião de {nome}", categoria="Estudo", inicio=agora, fim=agora + timedelta(hours=1))
        hoje = timezone.localdate()
        plano = Planejamento.objects.create(usuario_id=usuario.id, semana_inicio=hoje, semana_fim=hoje + timedelta(days=6))
        SessaoPlanejada.todas.create(planejamento=plano, atividade=tarefa, data=hoje, duracao_min=60)


class BaixarMeusDadosTests(DadosDaContaMixin, TestCase):

    def setUp(self):
        self.client.force_login(self.ana)

    def baixar(self):
        resposta = self.client.get(reverse("baixar_meus_dados"))
        self.assertEqual(resposta.status_code, 200)
        return resposta, json.loads(resposta.content.decode("utf-8"))

    def test_arquivo_vem_como_download_json(self):
        resposta, _ = self.baixar()
        self.assertTrue(resposta["Content-Type"].startswith("application/json"))
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn("timeline-meus-dados-", resposta["Content-Disposition"])
        self.assertIn("no-store", resposta["Cache-Control"])

    def test_inclui_conta_perfil_e_registros(self):
        _, dados = self.baixar()
        self.assertEqual(dados["conta"]["usuario"], "ana")
        self.assertEqual(dados["perfil"]["faculdade"], "PUC-Rio")
        titulos = [t["titulo"] for t in dados["tarefas"]]
        self.assertIn("Lista de Ana", titulos)
        self.assertEqual(dados["tarefas"][0]["etapas"] or dados["tarefas"][1]["etapas"], [{"titulo": "Questão 1", "concluida": False}])
        self.assertEqual(dados["compromissos"][0]["titulo"], "Reunião de Ana")
        self.assertEqual(len(dados["planejamentos"][0]["sessoes"]), 1)

    def test_inclui_o_que_esta_na_lixeira(self):
        _, dados = self.baixar()
        lixeira = [t for t in dados["tarefas"] if t["na_lixeira"]]
        self.assertEqual([t["titulo"] for t in lixeira], ["Tarefa na lixeira de Ana"])

    def test_nao_inclui_dados_de_outra_conta(self):
        resposta, _ = self.baixar()
        self.assertNotIn("Bia", resposta.content.decode("utf-8"))

    def test_nao_expoe_a_senha(self):
        resposta, _ = self.baixar()
        self.assertNotIn(self.ana.password, resposta.content.decode("utf-8"))

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("baixar_meus_dados")).status_code, 302)


class ExcluirContaTests(DadosDaContaMixin, TestCase):

    def setUp(self):
        self.client.force_login(self.ana)

    def excluir(self, **dados):
        return self.client.post(reverse("excluir_conta"), {"confirmacao": "senha-segura-123", "ciente": "on", **dados})

    def test_configuracoes_tem_os_botoes(self):
        resposta = self.client.get(reverse("configuracoes"))
        self.assertContains(resposta, reverse("baixar_meus_dados"))
        self.assertContains(resposta, reverse("excluir_conta"))

    def test_pagina_mostra_o_que_sera_apagado(self):
        resposta = self.client.get(reverse("excluir_conta"))
        self.assertContains(resposta, "2 tarefas")
        self.assertContains(resposta, "1 compromisso")
        self.assertContains(resposta, "1 planejamento")

    def test_excluir_apaga_a_conta_e_todos_os_dados(self):
        resposta = self.excluir()
        self.assertContains(resposta, "Sua conta foi excluída")
        self.assertFalse(get_user_model().objects.filter(username="ana").exists())
        self.assertFalse(PerfilAluno.objects.filter(nome_completo="Ana Silva").exists())
        self.assertFalse(Atividade.todos.filter(usuario_id=self.ana.id).exists())
        self.assertFalse(Compromisso.todos.filter(usuario_id=self.ana.id).exists())
        self.assertFalse(Planejamento.objects.filter(usuario_id=self.ana.id).exists())
        self.assertFalse(Subtarefa.objects.filter(titulo="Questão 1", atividade__usuario_id=self.ana.id).exists())

    def test_excluir_encerra_a_sessao(self):
        self.excluir()
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("hoje")).status_code, 302)

    def test_dados_de_outra_conta_continuam(self):
        self.excluir()
        self.assertTrue(get_user_model().objects.filter(username="bia").exists())
        self.assertEqual(Atividade.todos.filter(usuario_id=self.bia.id).count(), 2)
        self.assertEqual(Compromisso.todos.filter(usuario_id=self.bia.id).count(), 1)
        self.assertEqual(SessaoPlanejada.todas.filter(planejamento__usuario_id=self.bia.id).count(), 1)

    def test_senha_errada_nao_exclui(self):
        resposta = self.excluir(confirmacao="errada")
        self.assertContains(resposta, "Senha incorreta.")
        self.assertTrue(get_user_model().objects.filter(username="ana").exists())

    def test_sem_marcar_ciente_nao_exclui(self):
        resposta = self.client.post(reverse("excluir_conta"), {"confirmacao": "senha-segura-123"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("ciente", resposta.context["form"].errors)
        self.assertTrue(get_user_model().objects.filter(username="ana").exists())

    def test_get_nao_exclui(self):
        self.client.get(reverse("excluir_conta"))
        self.assertTrue(get_user_model().objects.filter(username="ana").exists())

    def test_conta_do_google_confirma_com_o_usuario(self):
        google = get_user_model().objects.create_user(username="carla")
        google.set_unusable_password()
        google.save()
        self.client.force_login(google)
        self.assertContains(self.client.get(reverse("excluir_conta")), "Digite seu usuário (carla)")
        self.client.post(reverse("excluir_conta"), {"confirmacao": "outro", "ciente": "on"})
        self.assertTrue(get_user_model().objects.filter(username="carla").exists())
        self.client.post(reverse("excluir_conta"), {"confirmacao": "carla", "ciente": "on"})
        self.assertFalse(get_user_model().objects.filter(username="carla").exists())

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("excluir_conta")).status_code, 302)
