from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AlertaCarga, Atividade, Planejamento


def criar_atividade(titulo, dias, **extra):
    """
    Cria uma atividade com prazo deslocado em dias a partir de agora.
    Dias negativos produzem uma atividade atrasada.
    """

    return Atividade.objects.create(
        usuario_id=extra.pop("usuario_id", 1),
        titulo=titulo,
        tipo=extra.pop("tipo", "lista"),
        prazo=timezone.now() + timedelta(days=dias),
        **extra,
    )


class NotificacoesTests(TestCase):
    """
    Cobre a página de notificações, que existia como template
    sem view e sem rota.
    """

    def test_a_rota_existe_e_responde(self):
        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "notificacoes.html")

    def test_atividade_vencida_entra_em_atrasadas(self):
        criar_atividade("Entrega de ontem", -1)

        resposta = self.client.get(reverse("notificacoes"))

        titulos = [a.titulo for a in resposta.context["atrasadas"]]

        self.assertEqual(titulos, ["Entrega de ontem"])

    def test_atividade_proxima_entra_na_lista_da_semana(self):
        criar_atividade("Lista de cálculo", 3)

        resposta = self.client.get(reverse("notificacoes"))

        titulos = [a.titulo for a in resposta.context["atividades"]]

        self.assertEqual(titulos, ["Lista de cálculo"])
        self.assertEqual(resposta.context["total_semana"], 1)

    def test_atividade_distante_fica_de_fora(self):
        criar_atividade("Prova do mês que vem", 30)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 0)

    def test_atividade_concluida_nao_gera_aviso(self):
        criar_atividade("Já entreguei", -2, status="concluida")

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(len(resposta.context["atrasadas"]), 0)
        self.assertEqual(resposta.context["total_semana"], 0)

    def test_atividade_de_outro_usuario_nao_aparece(self):
        criar_atividade("Da outra pessoa", 2, usuario_id=99)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 0)

    def test_sem_pendencias_nao_ha_avisos(self):
        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_avisos"], 0)
        self.assertContains(resposta, "Tudo em dia")

    def test_aviso_de_semana_cheia_a_partir_de_tres(self):
        for i in range(3):
            criar_atividade(f"Atividade {i}", i + 1)

        resposta = self.client.get(reverse("notificacoes"))

        self.assertEqual(resposta.context["total_semana"], 3)
        self.assertContains(resposta, "Semana com muitas atividades")


class AlertaDeCargaTests(TestCase):
    """
    O modelo AlertaCarga existia no projeto e nunca era populado.
    """

    def criar_planejamento(self, disponiveis, alocadas):
        hoje = timezone.localdate()
        segunda = hoje - timedelta(days=hoje.weekday())

        return Planejamento.objects.create(
            usuario_id=1,
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

        self.client.get(reverse("notificacoes"))
        self.client.get(reverse("notificacoes"))
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


class CadastrarAtividadeTests(TestCase):
    """
    O template cadastrar-atividade-cacau.html também estava órfão.
    """

    def test_a_rota_existe_e_responde(self):
        resposta = self.client.get(
            reverse("cadastrar_atividade_cacau")
        )

        self.assertEqual(resposta.status_code, 200)

    def test_cadastro_salva_e_volta_para_notificacoes(self):
        amanha = timezone.localdate() + timedelta(days=1)

        resposta = self.client.post(
            reverse("cadastrar_atividade_cacau"),
            {
                "titulo": "Lista de exercícios 5",
                "tipo": "lista",
                "nome_disciplina": " Cálculo 1 ",
                "data_entrega": amanha.isoformat(),
                "horario": "14:30",
            },
        )

        atividade = Atividade.objects.get(
            titulo="Lista de exercícios 5"
        )

        self.assertRedirects(resposta, reverse("notificacoes"))
        self.assertEqual(atividade.nome_disciplina, "Cálculo 1")
        self.assertEqual(
            timezone.localtime(atividade.prazo).strftime("%H:%M"),
            "14:30",
        )

    def test_sem_horario_o_prazo_vai_para_o_fim_do_dia(self):
        amanha = timezone.localdate() + timedelta(days=1)

        self.client.post(
            reverse("cadastrar_atividade_cacau"),
            {
                "titulo": "Leitura do capítulo 8",
                "tipo": "leitura",
                "nome_disciplina": "",
                "data_entrega": amanha.isoformat(),
                "horario": "",
            },
        )

        atividade = Atividade.objects.get(
            titulo="Leitura do capítulo 8"
        )

        self.assertEqual(
            timezone.localtime(atividade.prazo).strftime("%H:%M"),
            "23:59",
        )


class MenuDeNotificacoesTests(TestCase):
    """
    Nenhuma página do sistema levava às notificações.
    """

    def test_pagina_hoje_tem_link_para_notificacoes(self):
        resposta = self.client.get(reverse("hoje"))

        self.assertContains(resposta, reverse("notificacoes"))

    def test_pagina_adicionar_tarefa_tem_link_para_notificacoes(self):
        resposta = self.client.get(reverse("adicionar_tarefa"))

        self.assertContains(resposta, reverse("notificacoes"))

    def test_contador_aparece_quando_ha_aviso(self):
        criar_atividade("Entrega de ontem", -1)

        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["total_avisos"], 1)
        self.assertContains(resposta, "contador-avisos")

    def test_contador_some_quando_nao_ha_aviso(self):
        resposta = self.client.get(reverse("hoje"))

        self.assertEqual(resposta.context["total_avisos"], 0)
        self.assertNotContains(resposta, "contador-avisos")
