from datetime import date, datetime, time, timedelta
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from .models import Atividade, Aula, Compromisso, Disciplina, Planejamento, SessaoPlanejada, Subtarefa
from .forms import AtividadeRecorrenteForm, CompromissoRecorrenteForm
from .agenda_services import dados_periodo, horarios_livres, salvar_recorrencias, escapar_ics, dobrar_ics


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OrganizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="aluna", password="teste-123")
        self.other = get_user_model().objects.create_user(username="outra", password="teste-123")
        self.client.force_login(self.user)
        self.dia = timezone.localdate() + timedelta(days=14)
        self.tarefa = self.atividade()

    def instante(self, dia=None, hora=12):
        return timezone.make_aware(datetime.combine(dia or self.dia, time(hora)))

    def atividade(self, **kwargs):
        valores = dict(usuario_id=self.user.id, titulo="Trabalho", tipo="trabalho", prazo=self.instante(hora=23))
        valores.update(kwargs)
        return Atividade.objects.create(**valores)

    def plano(self):
        inicio = self.dia - timedelta(days=self.dia.weekday())
        return Planejamento.objects.create(usuario_id=self.user.id, semana_inicio=inicio, semana_fim=inicio+timedelta(days=6))

    def test_paginas_renderizam(self):
        for nome in ["tarefas", "agenda", "agenda_semana", "agenda_mes", "lixeira", "adicionar_tarefa", "novo_compromisso", "criar_sessao", "hoje", "planejamento", "progresso", "historico_planejamentos"]:
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_exige_login(self):
        self.client.logout()
        for nome in ["tarefas", "lixeira", "exportar_agenda", "criar_sessao"]:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302)

    def test_edita_tarefa_sem_recriar(self):
        r = self.client.post(reverse("editar_tarefa",args=[self.tarefa.id]),dict(titulo="Revisado", tipo="prova", nome_disciplina="Cálculo", data_entrega=self.dia.isoformat(), horario="15:30"))
        self.assertEqual(r.status_code,302)
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.titulo,"Revisado")
        self.assertEqual(timezone.localtime(self.tarefa.prazo).hour,15)
        self.assertEqual(Atividade.objects.count(),1)

    def test_edicao_invalida_preserva_formulario(self):
        r=self.client.post(reverse("editar_tarefa",args=[self.tarefa.id]),dict(titulo="Rascunho",tipo="prova",data_entrega="errada"))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,"Rascunho")
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.titulo,"Trabalho")

    def test_excluir_e_restaurar_preserva_etapas_sessoes(self):
        sub=Subtarefa.objects.create(atividade=self.tarefa,titulo="Pesquisar")
        sessao=SessaoPlanejada.objects.create(planejamento=self.plano(),atividade=self.tarefa,data=self.dia,hora_inicio=time(10),duracao_min=60)
        self.assertEqual(self.client.get(reverse("excluir_tarefa",args=[self.tarefa.id])).status_code,405)
        self.client.post(reverse("excluir_tarefa",args=[self.tarefa.id]))
        self.assertFalse(Atividade.objects.filter(pk=self.tarefa.pk).exists())
        self.assertFalse(SessaoPlanejada.objects.filter(pk=sessao.pk).exists())
        self.assertTrue(SessaoPlanejada.todas.filter(pk=sessao.pk).exists())
        self.assertContains(self.client.get(reverse("lixeira")),"Trabalho")
        self.client.post(reverse("restaurar",args=["tarefa",self.tarefa.id]))
        self.assertTrue(Atividade.objects.filter(pk=self.tarefa.pk).exists())
        self.assertTrue(SessaoPlanejada.objects.filter(pk=sessao.pk).exists())
        self.assertTrue(Subtarefa.objects.filter(pk=sub.pk).exists())

    def test_isolamento_entre_contas(self):
        outra=self.atividade(usuario_id=self.other.id,titulo="Segredo")
        self.assertNotContains(self.client.get(reverse("tarefas")),"Segredo")
        for nome in ["editar_tarefa","excluir_tarefa","alternar_status_tarefa","subtarefa"]:
            self.assertEqual(self.client.post(reverse(nome,args=[outra.id]),{"titulo":"Invadir"}).status_code,404)
        self.client.post(reverse("acoes_lote"),{"atividades":[outra.id],"acao":"excluir"})
        self.assertTrue(Atividade.objects.filter(pk=outra.pk).exists())

    def test_recorrencia_semanal_pelo_formulario(self):
        r=self.client.post(reverse("adicionar_tarefa"),dict(titulo="Lista semanal",tipo="lista",data_entrega=self.dia.isoformat(),horario="14:00",frequencia="semanal",repetir_ate=(self.dia+timedelta(days=14)).isoformat()))
        self.assertEqual(r.status_code,302)
        tarefas=list(Atividade.objects.filter(titulo="Lista semanal").order_by("prazo"))
        self.assertEqual(len(tarefas),3)
        self.assertEqual(len({t.serie_id for t in tarefas}),1)
        self.assertIsNotNone(tarefas[0].serie_id)
        self.assertEqual((tarefas[1].prazo-tarefas[0].prazo).days,7)

    def test_recorrencia_mensal_mantem_dia_original(self):
        objeto=Atividade(usuario_id=self.user.id,titulo="Mensal",tipo="lista",prazo=self.instante(date(2027,1,31)))
        salvar_recorrencias(objeto,"mensal",date(2027,3,31))
        self.assertEqual([timezone.localtime(t.prazo).date() for t in Atividade.objects.filter(titulo="Mensal").order_by("prazo")],[date(2027,1,31),date(2027,2,28),date(2027,3,31)])

    def test_recorrencia_exige_termino_e_limita_periodo(self):
        dados=dict(titulo="Repetida",tipo="lista",data_entrega=self.dia,frequencia="diaria")
        self.assertFalse(AtividadeRecorrenteForm(dados).is_valid())
        dados["repetir_ate"]=self.dia+timedelta(days=367)
        self.assertFalse(AtividadeRecorrenteForm(dados).is_valid())

    def test_compromisso_recorrente_e_lixeira(self):
        dados=dict(titulo="Aula extra",categoria="Estudo",inicio=self.instante(hora=10).strftime("%Y-%m-%dT%H:%M"),fim=self.instante(hora=11).strftime("%Y-%m-%dT%H:%M"),frequencia="diaria",repetir_ate=(self.dia+timedelta(days=2)).isoformat())
        self.assertEqual(self.client.post(reverse("novo_compromisso"),dados).status_code,302)
        self.assertEqual(Compromisso.objects.count(),3)
        c=Compromisso.objects.first()
        self.client.post(reverse("excluir_compromisso",args=[c.id]))
        self.assertEqual(Compromisso.objects.count(),2)
        self.client.post(reverse("restaurar",args=["compromisso",c.id]))
        self.assertEqual(Compromisso.objects.count(),3)
        dados["fim"]=dados["inicio"]
        self.assertFalse(CompromissoRecorrenteForm(dados).is_valid())

    def test_subtarefas_independentes(self):
        self.client.post(reverse("subtarefa",args=[self.tarefa.id]),{"titulo":"Pesquisar"})
        sub=self.tarefa.subtarefas.get()
        self.client.post(reverse("subtarefa",args=[self.tarefa.id]),{"subtarefa_id":sub.id})
        sub.refresh_from_db();self.tarefa.refresh_from_db()
        self.assertTrue(sub.concluida)
        self.assertEqual(self.tarefa.status,"planejada")

    def test_acoes_em_lote(self):
        outra=self.atividade(titulo="Segunda")
        ids=[self.tarefa.id,outra.id]
        self.client.post(reverse("acoes_lote"),{"atividades":ids,"acao":"concluir"})
        self.assertEqual(Atividade.objects.filter(status="concluida").count(),2)
        novo=self.dia+timedelta(days=1)
        self.client.post(reverse("acoes_lote"),{"atividades":ids,"acao":"adiar","nova_data":novo.isoformat()})
        self.tarefa.refresh_from_db()
        self.assertEqual(timezone.localtime(self.tarefa.prazo).date(),novo)
        self.assertEqual(timezone.localtime(self.tarefa.prazo).hour,23)
        self.client.post(reverse("acoes_lote"),{"atividades":ids,"acao":"excluir"})
        self.assertEqual(Atividade.objects.count(),0)

    def test_lote_invalido_nao_altera_dados(self):
        for dados in [{"atividades":[self.tarefa.id],"acao":"adiar","nova_data":"invalida"},{"atividades":["abc"],"acao":"excluir"},{"acao":"excluir"}]:
            self.client.post(reverse("acoes_lote"),dados)
        self.assertTrue(Atividade.objects.filter(pk=self.tarefa.id).exists())

    def test_livres_considera_aulas_compromissos_multidia_e_sessoes(self):
        disciplina=Disciplina.objects.create(periodo_id=1,nome="Cálculo")
        Aula.objects.create(disciplina=disciplina,dia_semana=self.dia.isoweekday(),hora_inicio=time(9),hora_fim=time(10))
        Compromisso.objects.create(usuario_id=self.user.id,titulo="Viagem",categoria="Outro",inicio=self.instante(self.dia-timedelta(days=1),22),fim=self.instante(hora=8))
        SessaoPlanejada.objects.create(planejamento=self.plano(),atividade=self.tarefa,data=self.dia,hora_inicio=time(11),duracao_min=60)
        livres=horarios_livres(dados_periodo(self.user.id,self.dia,self.dia)[0])
        self.assertEqual([(l["inicio"],l["fim"]) for l in livres],[(480,540),(600,660),(720,1380)])

    def test_reserva_sessao_e_rejeita_sobreposicao(self):
        dados=dict(atividade=self.tarefa.id,data=self.dia.isoformat(),hora_inicio="10:00",duracao_min=60)
        url=reverse("criar_sessao")
        self.assertEqual(self.client.post(url,dados).status_code,302)
        self.assertEqual(SessaoPlanejada.objects.count(),1)
        resposta=self.client.post(url,dados)
        self.assertEqual(resposta.status_code,200)
        self.assertContains(resposta,"ocupado")
        self.assertEqual(SessaoPlanejada.objects.count(),1)
        self.assertEqual(float(Planejamento.objects.get().horas_alocadas),1)

    def test_reserva_rejeita_prazo_e_horario_fora_janela(self):
        for dia,hora in [(self.dia+timedelta(days=1),"10:00"),(self.dia,"23:30"),(timezone.localdate()-timedelta(days=1),"10:00")]:
            r=self.client.post(reverse("criar_sessao"),dict(atividade=self.tarefa.id,data=dia.isoformat(),hora_inicio=hora,duracao_min=60))
            self.assertEqual(r.status_code,200)
        self.assertEqual(SessaoPlanejada.objects.count(),0)

    def test_semana_queries_constantes(self):
        with self.assertNumQueries(4):
            dados_periodo(self.user.id,self.dia,self.dia+timedelta(days=6))
        for i in range(15):
            self.atividade(titulo=f"Extra {i}")
        with self.assertNumQueries(4):
            dados_periodo(self.user.id,self.dia,self.dia+timedelta(days=6))

    def test_tarefas_paginacao_filtros_sem_n_mais_um(self):
        for i in range(25):
            self.atividade(titulo=f"Outra {i}")
        r=self.client.get(reverse("tarefas"),{"busca":"Outra","page":2})
        self.assertEqual(len(r.context["atividades"]),5)
        self.assertEqual(r.context["total"],25)
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse("tarefas"))
        self.assertLessEqual(len(queries),7)

    def test_exportacao_ics_escape_crlf_e_intervalo(self):
        self.tarefa.titulo="Revisão, cálculo; etapa\nBEGIN:VEVENT"
        self.tarefa.save()
        outra=self.atividade(usuario_id=self.other.id,titulo="Segredo")
        r=self.client.get(reverse("exportar_agenda"),{"inicio":self.dia.isoformat(),"fim":self.dia.isoformat()})
        self.assertEqual(r.status_code,200)
        self.assertIn("text/calendar",r["Content-Type"])
        self.assertIn("timeline.ics",r["Content-Disposition"])
        texto=r.content.decode()
        self.assertIn("Revisão\\, cálculo\\; etapa\\nBEGIN:VEVENT",texto)
        self.assertEqual(texto.split("\r\n").count("BEGIN:VEVENT"),1)
        self.assertNotIn("Segredo",texto)
        self.assertTrue(texto.endswith("END:VCALENDAR\r\n"))
        self.assertTrue(all(len(l.encode())<=75 for l in dobrar_ics("SUMMARY:"+"ç"*100).split("\r\n")))
        self.assertEqual(self.client.get(reverse("exportar_agenda"),{"inicio":"2027-01-01","fim":"2029-01-01"}).status_code,400)

    def test_agenda_semanal_mostra_sessao_e_horarios_livres(self):
        SessaoPlanejada.objects.create(planejamento=self.plano(),atividade=self.tarefa,data=self.dia,hora_inicio=time(10),duracao_min=60)
        r=self.client.get(reverse("agenda_semana"),{"semana":self.dia.isoformat()})
        self.assertContains(r,"Reservar estudo")
        self.assertContains(r,"Estudo: Trabalho")

    def test_lixeira_nao_exporta_nem_lista(self):
        self.client.post(reverse("excluir_tarefa",args=[self.tarefa.id]))
        self.assertEqual(self.client.get(reverse("tarefas")).context["total"], 0)
        r=self.client.get(reverse("exportar_agenda"),{"inicio":self.dia.isoformat(),"fim":self.dia.isoformat()})
        self.assertNotIn("SUMMARY:Trabalho",r.content.decode())

    def test_intervalo_livre_nunca_tem_menos_de_15_minutos(self):
        Compromisso.objects.create(usuario_id=self.user.id,titulo="Ocupado",categoria="Outro",inicio=self.instante(hora=7),fim=self.instante(hora=22)+timedelta(minutes=50))
        Compromisso.objects.create(usuario_id=self.user.id,titulo="Madrugada",categoria="Outro",inicio=self.instante(hora=23)+timedelta(minutes=30),fim=self.instante(self.dia+timedelta(days=1),1))
        self.assertEqual(horarios_livres(dados_periodo(self.user.id,self.dia,self.dia)[0]),[])

    def test_exporta_aulas_sessoes_e_multidia_sem_duplicar(self):
        disciplina=Disciplina.objects.create(periodo_id=1,nome="Cálculo")
        Aula.objects.create(disciplina=disciplina,dia_semana=self.dia.isoweekday(),hora_inicio=time(8),hora_fim=time(9))
        Compromisso.objects.create(usuario_id=self.user.id,titulo="Viagem",categoria="Outro",inicio=self.instante(hora=20),fim=self.instante(self.dia+timedelta(days=2),8))
        SessaoPlanejada.objects.create(planejamento=self.plano(),atividade=self.tarefa,data=self.dia,hora_inicio=time(10),duracao_min=60)
        resposta=self.client.get(reverse("exportar_agenda"),{"inicio":self.dia.isoformat(),"fim":(self.dia+timedelta(days=2)).isoformat()})
        texto=resposta.content.decode()
        self.assertEqual(texto.split("\r\n").count("BEGIN:VEVENT"),4)
        self.assertEqual(texto.count("SUMMARY:Viagem"),1)
        self.assertIn("SUMMARY:Estudo: Trabalho",texto)
        self.assertIn("SUMMARY:Cálculo",texto)

    def test_reserva_invalida_nao_usa_tarefa_de_outra_conta(self):
        outra=self.atividade(usuario_id=self.other.id)
        resposta=self.client.post(reverse("criar_sessao"),dict(atividade=outra.id,data=self.dia.isoformat(),hora_inicio="10:00",duracao_min=60))
        self.assertEqual(resposta.status_code,200)
        self.assertEqual(SessaoPlanejada.objects.count(),0)
