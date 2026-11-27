import json
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pywebpush import webpush, WebPushException

from core.models import (
    Atividade,
    InscricaoPush,
    LembreteEnviado
)


class Command(BaseCommand):
    help = "Envia notificacoes dos lembretes das tarefas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Verifica os lembretes a cada 30 segundos"
        )

    def handle(self, *args, **options):
        if not settings.VAPID_PRIVATE_KEY.is_file():
            raise CommandError("Chave VAPID privada nao encontrada.")

        self.stdout.write("Verificando lembretes...")

        if options["loop"]:
            try:
                while True:
                    self.verificar_lembretes()
                    time.sleep(30)

            except KeyboardInterrupt:
                self.stdout.write("Verificacao encerrada.")

        else:
            self.verificar_lembretes()

    def verificar_lembretes(self):
        agora = timezone.now()
        limite = agora - timedelta(minutes=5)

        atividades = Atividade.objects.filter(
            lembrete_minutos__isnull=False,
            excluido_em__isnull=True,
            prazo__gte=limite,
            prazo__lte=agora + timedelta(days=1)
        ).exclude(
            status__in=["concluida", "nao_concluida"]
        )

        for atividade in atividades:
            horario_lembrete = atividade.prazo - timedelta(
                minutes=atividade.lembrete_minutos
            )

            if not limite <= horario_lembrete <= agora:
                continue

            inscricoes = InscricaoPush.objects.filter(
                usuario_id=atividade.usuario_id
            )

            for inscricao in inscricoes:
                ja_enviado = LembreteEnviado.objects.filter(
                    atividade=atividade,
                    inscricao=inscricao,
                    horario_lembrete=horario_lembrete
                ).exists()

                if ja_enviado:
                    continue

                prazo_local = timezone.localtime(
                    atividade.prazo
                ).strftime("%d/%m às %H:%M")

                try:
                    webpush(
                        subscription_info={
                            "endpoint": inscricao.endpoint,
                            "keys": {
                                "p256dh": inscricao.p256dh,
                                "auth": inscricao.auth
                            }
                        },
                        data=json.dumps({
                            "titulo": "Timeline - Lembrete",
                            "mensagem": (
                                f"{atividade.titulo} - "
                                f"Prazo: {prazo_local}"
                            )
                        }),
                        vapid_private_key=str(
                            settings.VAPID_PRIVATE_KEY
                        ),
                        vapid_claims={
                            "sub": settings.VAPID_SUBJECT
                        },
                        ttl=300,
                        timeout=15
                    )

                except WebPushException as erro:
                    resposta = erro.response

                    if (
                        resposta is not None
                        and resposta.status_code in (404, 410)
                    ):
                        inscricao.delete()
                    else:
                        self.stderr.write(
                            "Falha no envio do lembrete."
                        )

                    continue

                except Exception:
                    self.stderr.write(
                        "Erro ao enviar notificacao."
                    )
                    continue

                LembreteEnviado.objects.get_or_create(
                    atividade=atividade,
                    inscricao=inscricao,
                    horario_lembrete=horario_lembrete
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Lembrete enviado: {atividade.titulo}"
                    )
                )