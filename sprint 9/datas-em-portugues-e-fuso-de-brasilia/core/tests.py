from datetime import date, datetime
from datetime import timezone as dt_timezone

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from django.utils.formats import date_format

from .models import Atividade


class LocalizacaoTests(TestCase):
    """
    Garante que o projeto usa português do Brasil e o fuso de Brasília.
    """

    def test_idioma_e_portugues_do_brasil(self):
        self.assertEqual(settings.LANGUAGE_CODE, "pt-br")

    def test_fuso_e_de_brasilia(self):
        self.assertEqual(settings.TIME_ZONE, "America/Sao_Paulo")

    def test_prazo_das_22h_usa_o_horario_de_brasilia(self):
        """
        Com o fuso em UTC, 22:00 era gravado como 22:00 UTC,
        que são 19:00 em Brasília: o prazo vencia 3 horas antes.
        """

        prazo = timezone.make_aware(datetime(2026, 11, 5, 22, 0))

        atividade = Atividade.objects.create(
            usuario_id=1,
            titulo="Entrega da noite",
            tipo="trabalho",
            prazo=prazo,
        )

        atividade.refresh_from_db()

        self.assertEqual(
            atividade.prazo,
            datetime(2026, 11, 6, 1, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            timezone.localtime(atividade.prazo).date(),
            date(2026, 11, 5),
        )

    def test_dia_atual_nao_muda_antes_da_meia_noite(self):
        """
        Com o fuso em UTC, às 21:30 de Brasília
        o sistema já considerava que era o dia seguinte.
        """

        instante = datetime(2026, 11, 6, 0, 30, tzinfo=dt_timezone.utc)

        self.assertEqual(
            timezone.localdate(instante),
            date(2026, 11, 5),
        )

    def test_nome_do_mes_sai_em_portugues(self):
        self.assertEqual(
            date_format(date(2026, 11, 1), "F"),
            "Novembro",
        )
