from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Compromisso


class EditarCompromissoTests(TestCase):
    """
    A agenda só deixava criar e excluir compromissos.
    Para corrigir um horário, era preciso apagar e cadastrar de novo.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="aluna_agenda")
        cls.outro = get_user_model().objects.create_user(username="outra_pessoa")

    def setUp(self):
        self.client.force_login(self.usuario)
        self.dia = timezone.localdate() + timedelta(days=2)
        self.compromisso = self.criar(self.usuario, "Reunião do grupo")

    def instante(self, hora, dia=None):
        return timezone.make_aware(datetime.combine(dia or self.dia, time(hora)))

    def criar(self, usuario, titulo):
        return Compromisso.objects.create(
            usuario_id=usuario.id,
            titulo=titulo,
            categoria="Estudo",
            inicio=self.instante(10),
            fim=self.instante(11),
        )

    def url(self, compromisso=None):
        return reverse("editar_compromisso", args=[(compromisso or self.compromisso).id])

    def dados(self, **extra):
        return {
            "titulo": "Reunião do grupo",
            "categoria": "Estudo",
            "inicio": self.instante(14).strftime("%Y-%m-%dT%H:%M"),
            "fim": self.instante(16).strftime("%Y-%m-%dT%H:%M"),
            **extra,
        }

    def test_formulario_vem_preenchido(self):
        resposta = self.client.get(self.url())
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Editar compromisso")
        self.assertContains(resposta, 'value="Reunião do grupo"')
        self.assertContains(resposta, self.instante(10).strftime("%Y-%m-%dT%H:%M"))

    def test_salvar_altera_o_mesmo_registro(self):
        self.client.post(self.url(), self.dados(titulo="Reunião remarcada"))
        self.compromisso.refresh_from_db()
        self.assertEqual(self.compromisso.titulo, "Reunião remarcada")
        self.assertEqual(timezone.localtime(self.compromisso.inicio).hour, 14)
        self.assertEqual(timezone.localtime(self.compromisso.fim).hour, 16)
        self.assertEqual(Compromisso.objects.count(), 1)

    def test_volta_para_a_semana_do_compromisso(self):
        outro_dia = self.dia + timedelta(days=14)
        resposta = self.client.post(self.url(), self.dados(
            inicio=self.instante(9, outro_dia).strftime("%Y-%m-%dT%H:%M"),
            fim=self.instante(10, outro_dia).strftime("%Y-%m-%dT%H:%M"),
        ))
        self.assertRedirects(
            resposta,
            f"{reverse('agenda_semana')}?semana={outro_dia.isoformat()}",
            fetch_redirect_response=False,
        )

    def test_termino_antes_do_inicio_e_recusado(self):
        resposta = self.client.post(self.url(), self.dados(
            fim=self.instante(13).strftime("%Y-%m-%dT%H:%M"),
        ))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("fim", resposta.context["form"].errors)
        self.compromisso.refresh_from_db()
        self.assertEqual(timezone.localtime(self.compromisso.inicio).hour, 10)

    def test_titulo_vazio_e_recusado(self):
        resposta = self.client.post(self.url(), self.dados(titulo=""))
        self.assertIn("titulo", resposta.context["form"].errors)

    def test_compromisso_de_outra_conta_devolve_404(self):
        alheio = self.criar(self.outro, "Compromisso alheio")
        self.assertEqual(self.client.get(self.url(alheio)).status_code, 404)
        self.client.post(self.url(alheio), self.dados(titulo="Invadido"))
        alheio.refresh_from_db()
        self.assertEqual(alheio.titulo, "Compromisso alheio")

    def test_compromisso_na_lixeira_nao_pode_ser_editado(self):
        self.compromisso.excluido_em = timezone.now()
        self.compromisso.save(update_fields=["excluido_em"])
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_editar_uma_ocorrencia_nao_muda_a_serie(self):
        self.client.post(reverse("novo_compromisso"), {
            **self.dados(titulo="Monitoria"),
            "frequencia": "diaria",
            "repetir_ate": (self.dia + timedelta(days=2)).isoformat(),
        })
        serie = Compromisso.objects.filter(titulo="Monitoria").order_by("inicio")
        self.assertEqual(serie.count(), 3)
        primeira = serie.first()
        self.client.post(self.url(primeira), self.dados(titulo="Monitoria cancelada"))
        self.assertEqual(Compromisso.objects.filter(titulo="Monitoria").count(), 2)

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_agenda_semanal_tem_o_link_de_editar(self):
        resposta = self.client.get(reverse("agenda_semana"), {"semana": self.dia.isoformat()})
        self.assertContains(resposta, self.url())

    def test_agenda_mensal_tem_o_link_de_editar(self):
        resposta = self.client.get(reverse("agenda_mes"), {"mes": self.dia.isoformat()})
        self.assertContains(resposta, self.url())

    def test_rotulos_aparecem_com_acento(self):
        resposta = self.client.get(self.url())
        for rotulo in ("Título", "Início", "Término", "Horário flexível"):
            self.assertContains(resposta, rotulo)

    def test_serie_avisa_que_so_esta_ocorrencia_muda(self):
        import uuid
        self.compromisso.serie_id = uuid.uuid4()
        self.compromisso.save(update_fields=["serie_id"])
        self.assertContains(self.client.get(self.url()), "vale só para esta ocorrência")
