from datetime import datetime, time, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Atividade, Compromisso, Subtarefa
from .agenda_services import dados_periodo, horarios_livres, salvar_recorrencias


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FluxosTarefasTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="fluxos")
        self.outro = get_user_model().objects.create_user(username="outra_conta")
        self.client.force_login(self.usuario)
        self.dia = timezone.localdate() + timedelta(days=10)

    def instante(self, hora=13, dia=None):
        return timezone.make_aware(datetime.combine(dia or self.dia, time(hora)))

    def criar(self, **extra):
        dados = dict(usuario_id=self.usuario.id, titulo="Estudar", tipo="lista", prazo=self.instante(), duracao_estimada_min=60)
        dados.update(extra)
        return Atividade.objects.create(**dados)

    def dados(self, **extra):
        dados = dict(titulo="Estudar", tipo="lista", nome_disciplina="Calculo", data_entrega=self.dia.isoformat(), horario="13:00", horario_fim="14:00")
        dados.update(extra)
        return dados

    def livres(self):
        dia = dados_periodo(self.usuario.id, self.dia, self.dia)[0]
        return [(l["inicio"], l["fim"]) for l in horarios_livres(dia)]

    def test_altera_apenas_quatro_selecionadas_e_preserva_filtros(self):
        tarefas = [self.criar(titulo=f"Lista {i}") for i in range(7)]
        alheia = self.criar(usuario_id=self.outro.id)
        nova_data = self.dia + timedelta(days=2)
        retorno = "busca=Lista&tipo=lista&ordem=titulo&page=1"
        resposta = self.client.post(reverse("acoes_lote"), {"atividades": [t.pk for t in tarefas[:4]]+[alheia.pk], "acao": "adiar", "nova_data": nova_data.isoformat(), "retorno": retorno})
        self.assertEqual(parse_qs(urlparse(resposta.url).query), parse_qs(retorno))
        for indice, tarefa in enumerate(tarefas):
            tarefa.refresh_from_db()
            self.assertEqual(timezone.localtime(tarefa.prazo).date(), nova_data if indice < 4 else self.dia)
            self.assertEqual(timezone.localtime(tarefa.prazo).time(), time(13))
        alheia.refresh_from_db()
        self.assertEqual(timezone.localtime(alheia.prazo).date(), self.dia)

    def test_filtros_combinados_e_paginacao(self):
        for i in range(25):
            self.criar(titulo=f"Revisao {i}", serie_id="12345678-1234-1234-1234-123456789012")
        self.criar(titulo="Outra", tipo="prova")
        self.criar(titulo="Revisao concluida", status="concluida")
        resposta = self.client.get(reverse("tarefas"), {"busca": "Revisao", "tipo": "lista", "status": "planejada", "recorrencia": "sim", "page": 2})
        self.assertEqual(resposta.context["total"], 25)
        self.assertEqual(len(resposta.context["atividades"]), 5)
        self.assertContains(resposta, "recorrencia=sim")

    def test_horario_de_13_a_14_libera_antes_e_depois(self):
        self.criar()
        self.assertEqual(self.livres(), [(360, 780), (840, 1380)])

    def test_intervalos_sobrepostos_sao_unificados(self):
        self.criar(duracao_estimada_min=120)
        Compromisso.objects.create(usuario_id=self.usuario.id, titulo="Reuniao", categoria="Outro", inicio=self.instante(14), fim=self.instante(16))
        self.assertEqual(self.livres(), [(360, 780), (960, 1380)])

    def test_hoje_mostra_antes_da_tarefa_mas_nao_reserva_passado(self):
        self.dia = timezone.localdate()
        self.criar()
        original = timezone.localtime
        with patch("core.agenda_services.timezone.localtime", wraps=original) as local:
            local.side_effect = lambda value=None: original(value) if value else self.instante(15)
            dia = dados_periodo(self.usuario.id, self.dia, self.dia)[0]
            self.assertEqual([(l["inicio"], l["fim"]) for l in horarios_livres(dia)], [(360, 780), (840, 1380)])
            self.assertFalse(horarios_livres(dia)[0]["reservavel"])
            self.assertEqual(horarios_livres(dia, para_reserva=True)[0]["inicio"], 915)

    def test_duracao_do_formulario_e_fim_invalido(self):
        resposta = self.client.post(reverse("adicionar_tarefa"), self.dados(horario_fim="15:30"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Atividade.objects.get().duracao_estimada_min, 150)
        resposta = self.client.post(reverse("adicionar_tarefa"), self.dados(horario_fim="12:00"))
        self.assertContains(resposta, "O término deve ser depois do início")
        self.assertEqual(Atividade.objects.count(), 1)

    def test_subetapas_concluem_reabrem_e_nova_etapa_reabre(self):
        tarefa = self.criar()
        etapas = [Subtarefa.objects.create(atividade=tarefa, titulo=f"Etapa {i}") for i in range(2)]
        url = reverse("subtarefa", args=[tarefa.pk])
        self.client.post(url, {"subtarefa_id": etapas[0].pk})
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, "planejada")
        self.client.post(url, {"subtarefa_id": etapas[1].pk})
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, "concluida")
        self.client.post(url, {"subtarefa_id": etapas[1].pk})
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, "em_andamento")
        self.client.post(url, {"subtarefa_id": etapas[1].pk})
        self.client.post(url, {"titulo": "Nova etapa"})
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, "em_andamento")

    def test_recorrencia_diaria_inclusiva_e_duracao(self):
        ate = self.dia + timedelta(days=3)
        self.client.post(reverse("adicionar_tarefa"), self.dados(frequencia="diaria", repetir_ate=ate.isoformat()))
        tarefas = list(Atividade.objects.order_by("prazo"))
        self.assertEqual(len(tarefas), 4)
        self.assertEqual({t.repetir_ate for t in tarefas}, {ate})
        self.assertEqual({t.duracao_estimada_min for t in tarefas}, {60})
        self.assertEqual(len({t.serie_id for t in tarefas}), 1)
        for i, tarefa in enumerate(tarefas):
            self.assertEqual(timezone.localtime(tarefa.prazo).date(), self.dia + timedelta(days=i))

    def test_editar_proximas_preserva_anteriores_e_nao_duplica(self):
        tarefa = self.criar()
        salvar_recorrencias(tarefa, "semanal", self.dia+timedelta(days=21))
        tarefas = list(Atividade.objects.order_by("prazo"))
        etapa = Subtarefa.objects.create(atividade=tarefas[2], titulo="Preservar etapa", concluida=True)
        dados = self.dados(titulo="Atualizada", data_entrega=(self.dia+timedelta(days=7)).isoformat(), frequencia="semanal", repetir_ate=(self.dia+timedelta(days=28)).isoformat(), aplicar_a="proximas")
        url = reverse("editar_tarefa", args=[tarefas[1].pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(Atividade.objects.count(), 5)
        tarefas[0].refresh_from_db()
        self.assertEqual(tarefas[0].titulo, "Estudar")
        self.assertEqual(Atividade.objects.filter(titulo="Atualizada").count(), 4)
        etapa.refresh_from_db()
        self.assertTrue(etapa.concluida)

    def test_parar_repeticao_move_proximas_para_lixeira(self):
        tarefa = self.criar()
        salvar_recorrencias(tarefa, "diaria", self.dia+timedelta(days=3))
        resposta = self.client.post(reverse("editar_tarefa", args=[tarefa.pk]), self.dados(aplicar_a="proximas", frequencia="", repetir_ate=""))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Atividade.objects.count(), 1)
        self.assertEqual(Atividade.todos.filter(excluido_em__isnull=False).count(), 3)

    def test_mudar_uma_ocorrencia_nao_altera_outras(self):
        tarefa = self.criar()
        ate = self.dia + timedelta(days=2)
        salvar_recorrencias(tarefa, "diaria", ate)
        resposta = self.client.post(reverse("editar_tarefa", args=[tarefa.pk]), self.dados(titulo="Excecao", aplicar_a="esta", frequencia="diaria", repetir_ate=ate.isoformat()))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Atividade.objects.filter(titulo="Excecao").count(), 1)
        self.assertEqual(Atividade.objects.filter(titulo="Estudar").count(), 2)

    def test_recorrencia_invalida_nao_salva_nenhuma_ocorrencia(self):
        resposta = self.client.post(reverse("adicionar_tarefa"), self.dados(frequencia="semanal", repetir_ate=(self.dia-timedelta(days=1)).isoformat()))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Atividade.objects.count(), 0)
        with self.assertRaises(ValueError):
            salvar_recorrencias(Atividade(usuario_id=self.usuario.id, titulo="Invalida", tipo="lista", prazo=self.instante()), "desconhecida", self.dia)
        self.assertEqual(Atividade.objects.count(), 0)
