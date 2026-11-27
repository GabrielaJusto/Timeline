from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PerfilAluno


class EditarPerfilTests(TestCase):
    """
    A tela de Configurações mostrava a conta, mas não deixava mudar nada:
    nome, faculdade, nascimento e e-mail ficavam presos ao cadastro.
    """

    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.usuario = U.objects.create_user(
            username="ana", email="ana@exemplo.test", password="senha-antiga-123",
            first_name="Ana", last_name="Silva",
        )
        PerfilAluno.objects.create(
            usuario=cls.usuario, nome_completo="Ana Silva",
            faculdade="PUC-Rio", data_nascimento=date(2003, 4, 10),
        )
        cls.outra = U.objects.create_user(username="bia", email="bia@exemplo.test")

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados(self, **extra):
        return {
            "nome_completo": "Ana Maria Silva",
            "faculdade": "UFRJ",
            "data_nascimento": "2003-04-10",
            "email": "ana.maria@exemplo.test",
            **extra,
        }

    def test_configuracoes_tem_os_botoes(self):
        resposta = self.client.get(reverse("configuracoes"))
        self.assertContains(resposta, reverse("editar_perfil"))
        self.assertContains(resposta, reverse("alterar_senha"))

    def test_formulario_vem_preenchido(self):
        resposta = self.client.get(reverse("editar_perfil"))
        self.assertContains(resposta, 'value="Ana Silva"')
        self.assertContains(resposta, 'value="PUC-Rio"')
        self.assertContains(resposta, 'value="2003-04-10"')
        self.assertContains(resposta, 'value="ana@exemplo.test"')

    def test_salvar_atualiza_perfil_e_conta(self):
        resposta = self.client.post(reverse("editar_perfil"), self.dados())
        self.assertRedirects(resposta, reverse("configuracoes"))
        self.usuario.refresh_from_db()
        perfil = self.usuario.perfil_aluno
        self.assertEqual(perfil.nome_completo, "Ana Maria Silva")
        self.assertEqual(perfil.faculdade, "UFRJ")
        self.assertEqual(self.usuario.email, "ana.maria@exemplo.test")
        self.assertEqual(self.usuario.first_name, "Ana")
        self.assertEqual(self.usuario.last_name, "Maria Silva")

    def test_configuracoes_confirma_a_alteracao(self):
        resposta = self.client.post(reverse("editar_perfil"), self.dados(), follow=True)
        self.assertContains(resposta, "Perfil atualizado.")
        self.assertContains(resposta, "Ana Maria Silva")

    def test_espacos_repetidos_no_nome_sao_removidos(self):
        self.client.post(reverse("editar_perfil"), self.dados(nome_completo="  Ana   Maria  "))
        self.assertEqual(PerfilAluno.objects.get(usuario=self.usuario).nome_completo, "Ana Maria")

    def test_email_de_outra_conta_e_recusado(self):
        resposta = self.client.post(reverse("editar_perfil"), self.dados(email="BIA@exemplo.test"))
        self.assertIn("email", resposta.context["form"].errors)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "ana@exemplo.test")

    def test_manter_o_proprio_email_e_permitido(self):
        resposta = self.client.post(reverse("editar_perfil"), self.dados(email="ana@exemplo.test"))
        self.assertRedirects(resposta, reverse("configuracoes"))

    def test_nascimento_no_futuro_e_recusado(self):
        amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
        resposta = self.client.post(reverse("editar_perfil"), self.dados(data_nascimento=amanha))
        self.assertIn("data_nascimento", resposta.context["form"].errors)

    def test_nome_e_faculdade_vazios_sao_recusados(self):
        resposta = self.client.post(reverse("editar_perfil"), self.dados(nome_completo="   ", faculdade=""))
        erros = resposta.context["form"].errors
        self.assertIn("nome_completo", erros)
        self.assertIn("faculdade", erros)
        self.assertEqual(PerfilAluno.objects.get(usuario=self.usuario).faculdade, "PUC-Rio")

    def test_conta_sem_perfil_ganha_um_ao_salvar(self):
        self.client.force_login(self.outra)
        self.client.post(reverse("editar_perfil"), self.dados(email="bia.nova@exemplo.test"))
        self.assertTrue(PerfilAluno.objects.filter(usuario=self.outra).exists())

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("editar_perfil")).status_code, 302)
        self.assertEqual(self.client.get(reverse("alterar_senha")).status_code, 302)


class AlterarSenhaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="caio", password="senha-antiga-123")

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_troca_de_senha_mantem_a_sessao(self):
        resposta = self.client.post(reverse("alterar_senha"), {
            "old_password": "senha-antiga-123",
            "new_password1": "Planejar-Com-Calma-2026",
            "new_password2": "Planejar-Com-Calma-2026",
        })
        self.assertRedirects(resposta, reverse("configuracoes"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Planejar-Com-Calma-2026"))
        # Continua conectado depois da troca.
        self.assertEqual(self.client.get(reverse("configuracoes")).status_code, 200)

    def test_senha_atual_errada_e_recusada(self):
        resposta = self.client.post(reverse("alterar_senha"), {
            "old_password": "errada",
            "new_password1": "Planejar-Com-Calma-2026",
            "new_password2": "Planejar-Com-Calma-2026",
        })
        self.assertIn("old_password", resposta.context["form"].errors)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha-antiga-123"))

    def test_conta_do_google_cria_senha_sem_pedir_a_atual(self):
        google = get_user_model().objects.create_user(username="google_user")
        google.set_unusable_password()
        google.save()
        self.client.force_login(google)
        resposta = self.client.get(reverse("alterar_senha"))
        self.assertContains(resposta, "Criar senha")
        self.assertNotContains(resposta, 'name="old_password"')
        self.client.post(reverse("alterar_senha"), {
            "new_password1": "Planejar-Com-Calma-2026",
            "new_password2": "Planejar-Com-Calma-2026",
        })
        google.refresh_from_db()
        self.assertTrue(google.check_password("Planejar-Com-Calma-2026"))


class EstiloDasConfiguracoesTests(TestCase):

    def test_folha_de_estilo_nao_tem_regra_aberta(self):
        # Uma regra sem "}" fazia o navegador ignorar o resto do arquivo,
        # inclusive o estilo dos formulários de perfil e senha.
        from pathlib import Path
        css = (Path(__file__).parent / "static/css/configuracoes.css").read_text(encoding="utf-8")
        self.assertEqual(css.count("{"), css.count("}"))
