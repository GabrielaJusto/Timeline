from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Atividade


class TaskCreationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user(pk=1, username="aluna_tarefas")

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
