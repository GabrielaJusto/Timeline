from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Atividade, PerfilAluno


class ConfiguracoesTests(TestCase):
    """
    A tela de Configurações descrevia o Timeline como um protótipo
    sem login, com as tarefas presas ao navegador e visíveis para
    quem usasse a mesma máquina. Nada disso vale desde que o projeto
    ganhou contas de verdade.
    """

    def setUp(self):
        Usuario = get_user_model()

        self.usuario = Usuario.objects.create_user(
            username="estudante",
            password="senha-de-teste-123",
            email="estudante@exemplo.com",
        )

        self.client.force_login(self.usuario)

    def criar_perfil(self):
        return PerfilAluno.objects.create(
            usuario=self.usuario,
            nome_completo="Maria Souza",
            faculdade="PUC-Rio",
            data_nascimento=date(2004, 3, 17),
        )

    def test_exige_login(self):
        self.client.logout()

        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.status_code, 302)

    def test_nao_afirma_mais_que_e_sem_login(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertNotContains(resposta, "sem login")
        self.assertNotContains(resposta, "sem cadastro")
        self.assertNotContains(resposta, "Vinculado a este navegador")

    def test_nao_diz_que_outra_pessoa_ve_as_tarefas(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertNotContains(
            resposta,
            "Quem usar este mesmo navegador",
        )

    def test_mostra_o_usuario_e_o_email(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertContains(resposta, "estudante")
        self.assertContains(resposta, "estudante@exemplo.com")

    def test_mostra_os_dados_do_perfil(self):
        self.criar_perfil()

        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.context["nome"], "Maria Souza")
        self.assertEqual(resposta.context["faculdade"], "PUC-Rio")
        self.assertContains(resposta, "PUC-Rio")
        self.assertContains(resposta, "17/03/2004")

    def test_sem_perfil_cai_no_nome_de_usuario(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertIsNone(resposta.context["perfil"])
        self.assertEqual(resposta.context["nome"], "estudante")

    def test_sem_perfil_nao_quebra_a_pagina(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Não informada")

    def test_mostra_o_fuso_configurado_no_projeto(self):
        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.context["fuso"], settings.TIME_ZONE)
        self.assertContains(resposta, settings.TIME_ZONE)
        self.assertNotContains(resposta, "Fuso local do dispositivo")

    def test_conta_as_tarefas_do_usuario(self):
        for i in range(3):
            Atividade.objects.create(
                usuario_id=self.usuario.id,
                titulo=f"Tarefa {i}",
                tipo="lista",
                prazo=timezone.now() + timedelta(days=i + 1),
            )

        Atividade.objects.create(
            usuario_id=9999,
            titulo="De outra pessoa",
            tipo="lista",
            prazo=timezone.now() + timedelta(days=1),
        )

        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.context["total_tarefas"], 3)

    def test_tarefa_na_lixeira_nao_conta(self):
        atividade = Atividade.objects.create(
            usuario_id=self.usuario.id,
            titulo="Mandei para a lixeira",
            tipo="lista",
            prazo=timezone.now() + timedelta(days=1),
        )
        atividade.excluido_em = timezone.now()
        atividade.save(update_fields=["excluido_em"])

        resposta = self.client.get(reverse("configuracoes"))

        self.assertEqual(resposta.context["total_tarefas"], 0)


class AvisoDaTelaHojeTests(TestCase):
    """
    O mesmo texto desatualizado aparecia na tela Hoje.
    """

    def setUp(self):
        Usuario = get_user_model()

        self.usuario = Usuario.objects.create_user(
            username="estudante",
            password="senha-de-teste-123",
        )

        self.client.force_login(self.usuario)

    def test_tela_hoje_nao_fala_mais_em_sem_login(self):
        resposta = self.client.get(reverse("hoje"))

        self.assertNotContains(resposta, "sem login")
        self.assertNotContains(
            resposta,
            "O acesso fica vinculado a este navegador",
        )
