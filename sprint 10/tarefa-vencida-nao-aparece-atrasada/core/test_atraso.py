from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Atividade


class BaseAtraso(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        self.usuario = Usuario.objects.create_user(
            username="estudante",
            password="senha-de-teste-123",
        )

        self.client.force_login(self.usuario)

    def criar(self, titulo, dias, **extra):
        return Atividade.objects.create(
            usuario_id=extra.pop("usuario_id", self.usuario.id),
            titulo=titulo,
            tipo=extra.pop("tipo", "lista"),
            prazo=timezone.now() + timedelta(days=dias),
            **extra,
        )


class PropriedadeAtrasadaTests(BaseAtraso):
    """
    O status "Atrasada" existe no modelo desde o início e nunca era
    atribuído a registro nenhum. Tarefa com prazo vencido continuava
    aparecendo como "Planejada".
    """

    def test_prazo_vencido_e_pendente_esta_atrasada(self):
        atividade = self.criar("Venceu ontem", -1)

        self.assertTrue(atividade.esta_atrasada)

    def test_prazo_futuro_nao_esta_atrasada(self):
        atividade = self.criar("Vence amanha", 1)

        self.assertFalse(atividade.esta_atrasada)

    def test_concluida_fora_do_prazo_nao_conta_como_atrasada(self):
        atividade = self.criar("Entreguei atrasado", -3, status="concluida")

        self.assertFalse(atividade.esta_atrasada)

    def test_nao_concluida_nao_conta_como_atrasada(self):
        atividade = self.criar("Desisti", -3, status="nao_concluida")

        self.assertFalse(atividade.esta_atrasada)

    def test_em_andamento_vencida_esta_atrasada(self):
        atividade = self.criar("Comecei e parei", -2, status="em_andamento")

        self.assertTrue(atividade.esta_atrasada)

    def test_nao_grava_nada_no_banco(self):
        """
        O atraso é derivado do prazo; o status escolhido continua intacto.
        """

        atividade = self.criar("Venceu ontem", -1)

        self.assertTrue(atividade.esta_atrasada)

        atividade.refresh_from_db()

        self.assertEqual(atividade.status, "planejada")


class EtiquetaNaListaTests(BaseAtraso):
    def test_lista_mostra_a_etiqueta_na_tarefa_vencida(self):
        self.criar("Venceu ontem", -1)

        resposta = self.client.get(reverse("tarefas"))

        self.assertContains(resposta, "org-atrasada")
        self.assertContains(resposta, "Atrasada")

    def test_lista_nao_marca_tarefa_em_dia(self):
        self.criar("Vence amanha", 1)

        resposta = self.client.get(reverse("tarefas"))

        self.assertNotContains(resposta, "org-atrasada")


class FiltroAtrasadaTests(BaseAtraso):
    """
    O filtro de status oferecia "Atrasada", mas como nada gravava esse
    status, escolher a opção devolvia sempre uma lista vazia.
    """

    def titulos(self, resposta):
        return [a.titulo for a in resposta.context["atividades"]]

    def test_filtro_traz_as_vencidas(self):
        self.criar("Venceu ontem", -1)
        self.criar("Venceu semana passada", -7)
        self.criar("Vence amanha", 1)

        resposta = self.client.get(
            reverse("tarefas"),
            {"status": "atrasada"},
        )

        self.assertEqual(
            sorted(self.titulos(resposta)),
            ["Venceu ontem", "Venceu semana passada"],
        )

    def test_filtro_ignora_as_concluidas(self):
        self.criar("Entreguei atrasado", -2, status="concluida")

        resposta = self.client.get(
            reverse("tarefas"),
            {"status": "atrasada"},
        )

        self.assertEqual(self.titulos(resposta), [])

    def test_filtro_nao_mistura_usuarios(self):
        self.criar("Da outra pessoa", -1, usuario_id=9999)

        resposta = self.client.get(
            reverse("tarefas"),
            {"status": "atrasada"},
        )

        self.assertEqual(self.titulos(resposta), [])

    def test_outros_filtros_de_status_continuam_funcionando(self):
        self.criar("Feita", 1, status="concluida")
        self.criar("Pendente", 2)

        resposta = self.client.get(
            reverse("tarefas"),
            {"status": "concluida"},
        )

        self.assertEqual(self.titulos(resposta), ["Feita"])

    def test_sem_filtro_mostra_tudo(self):
        self.criar("Venceu ontem", -1)
        self.criar("Vence amanha", 1)

        resposta = self.client.get(reverse("tarefas"))

        self.assertEqual(len(self.titulos(resposta)), 2)
