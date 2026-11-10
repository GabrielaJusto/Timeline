from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Atividade


class TaskCreationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user(pk=1, username="aluna_tarefas")

    def setUp(self):
        self.client.force_login(get_user_model().objects.get(pk=1))

    def task_data(self):
        return {
            "titulo": "Revisar conteúdo", "tipo": Atividade.TIPOS[0][0],
            "data_entrega": "2026-12-15", "horario": "14:00",
            "nome_disciplina": "Matemática",
        }

    def test_form_has_no_hoje_background(self):
        response = self.client.get(reverse("adicionar_tarefa"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="conteudo-principal"')
        self.assertContains(response, 'class="modal"')

    def test_direct_creation_redirects_to_task_list(self):
        response = self.client.post(reverse("adicionar_tarefa"), self.task_data())
        self.assertRedirects(response, reverse("tarefas"))
        task = Atividade.objects.get(titulo="Revisar conteúdo")
        self.assertEqual(task.nome_disciplina, "Matemática")
        self.assertIsNotNone(task.prazo)

    def test_modal_creation_returns_task_list_destination(self):
        response = self.client.post(reverse("adicionar_tarefa"), self.task_data(), HTTP_X_TASK_MODAL="1")
        self.assertEqual(response.json(), {"redirect": reverse("tarefas")})
        self.assertEqual(Atividade.objects.count(), 1)

    def test_invalid_modal_form_preserves_input_and_creates_no_task(self):
        response = self.client.post(reverse("adicionar_tarefa"), {
            "titulo": "Minha tarefa", "data_entrega": "data inválida",
        }, HTTP_X_TASK_MODAL="1")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(response.context["form"]["titulo"].value(), "Minha tarefa")
        self.assertEqual(Atividade.objects.count(), 0)

    def test_modal_recorrente_preserva_proprietario_e_retorno(self):
        dados = {**self.task_data(), "frequencia": "semanal", "repetir_ate": "2026-12-29"}
        response = self.client.post(reverse("adicionar_tarefa"), dados, HTTP_X_TASK_MODAL="1")
        self.assertEqual(response.json(), {"redirect": reverse("tarefas")})
        tarefas = Atividade.objects.filter(titulo=dados["titulo"])
        self.assertEqual(tarefas.count(), 3)
        self.assertEqual(set(tarefas.values_list("usuario_id", flat=True)), {1})
        self.assertEqual(len(set(tarefas.values_list("serie_id", flat=True))), 1)

    def test_lista_preserva_marca_modal_e_acoes_de_organizacao(self):
        tarefa = Atividade.objects.create(usuario_id=1, titulo="Integração", tipo="prova", prazo="2026-12-15T14:00:00-03:00")
        response = self.client.get(reverse("tarefas"))
        self.assertContains(response, "timeline-brand")
        self.assertContains(response, "tarefa-modal.js")
        self.assertContains(response, reverse("editar_tarefa", args=[tarefa.id]))
        self.assertContains(response, reverse("subtarefa", args=[tarefa.id]))
        self.assertContains(response, reverse("acoes_lote"))

    def test_visitante_nao_expoe_tarefas_de_contas(self):
        Atividade.objects.create(usuario_id=1, titulo="Tarefa privada", tipo="prova", prazo="2026-12-15T14:00:00-03:00")
        response = self.client.get(reverse("continuar_visitante"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Tarefa privada")
        self.assertNotIn("_auth_user_id", self.client.session)
