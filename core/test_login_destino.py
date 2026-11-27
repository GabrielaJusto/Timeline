from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LoginVoltaParaAPaginaPedidaTests(TestCase):
    """
    Quem abria uma página protegida sem estar logado ia para
    /login/?next=<página>, mas depois de entrar caía sempre em Hoje.
    """

    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user(username="ana", password="senha-segura-123")

    def entrar(self, next_=None, senha="senha-segura-123", pela_url=False):
        dados = {"username": "ana", "password": senha}
        url = reverse("login")
        if next_ is not None and pela_url:
            url = f"{url}?next={next_}"
        elif next_ is not None:
            dados["next"] = next_
        return self.client.post(url, dados)

    def test_pagina_protegida_manda_para_o_login_com_next(self):
        resposta = self.client.get(reverse("tarefas"))
        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('tarefas')}", fetch_redirect_response=False)

    def test_formulario_guarda_a_pagina_pedida(self):
        resposta = self.client.get(reverse("login"), {"next": "/tarefas/"})
        self.assertContains(resposta, 'name="next" value="/tarefas/"')

    def test_volta_para_a_pagina_pedida(self):
        resposta = self.entrar("/tarefas/?status=planejada")
        self.assertRedirects(resposta, "/tarefas/?status=planejada", fetch_redirect_response=False)

    def test_next_pela_url_tambem_funciona(self):
        resposta = self.entrar("/progresso/", pela_url=True)
        self.assertRedirects(resposta, "/progresso/", fetch_redirect_response=False)

    def test_sem_next_continua_indo_para_hoje(self):
        resposta = self.entrar()
        self.assertRedirects(resposta, reverse("hoje"), fetch_redirect_response=False)

    def test_endereco_de_outro_site_e_ignorado(self):
        for perigoso in ("https://site-falso.com/", "//site-falso.com/", "javascript:alert(1)"):
            self.client.logout()
            resposta = self.entrar(perigoso)
            self.assertRedirects(resposta, reverse("hoje"), fetch_redirect_response=False, msg_prefix=perigoso)

    def test_senha_errada_mantem_usuario_e_pagina_pedida(self):
        resposta = self.entrar("/tarefas/", senha="errada")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário ou senha incorretos.")
        self.assertContains(resposta, 'value="ana"')
        self.assertContains(resposta, 'name="next" value="/tarefas/"')
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_quem_ja_esta_logado_vai_direto_para_a_pagina_pedida(self):
        self.entrar()
        resposta = self.client.get(reverse("login"), {"next": "/configuracoes/"})
        self.assertRedirects(resposta, "/configuracoes/", fetch_redirect_response=False)

    def test_next_com_aspas_nao_quebra_o_html(self):
        resposta = self.client.get(reverse("login"), {"next": '/tarefas/"><script>x</script>'})
        self.assertNotContains(resposta, "<script>x</script>")
