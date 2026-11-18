"""Recorrência, intervalos e exportação compartilhados pelas telas da agenda."""
import calendar
import uuid
from datetime import datetime, time, timedelta
from django.db import transaction
from django.utils import timezone
from .models import Atividade, Aula, Compromisso, SessaoPlanejada


def limites(dia):
    return (timezone.make_aware(datetime.combine(dia, time.min)),
            timezone.make_aware(datetime.combine(dia + timedelta(days=1), time.min)))


def datas_recorrencia(original, frequencia, ate):
    if frequencia not in ("", "diaria", "semanal", "mensal"):
        raise ValueError("Frequência inválida")
    if frequencia and (not ate or ate < original.date() or (ate-original.date()).days > 366):
        raise ValueError("Informe um término entre a primeira ocorrência e os próximos 366 dias.")
    datas = [original]
    if not frequencia:
        return datas
    for indice in range(1, 368):
        if frequencia == "mensal":
            mes = original.month - 1 + indice
            ano, mes = original.year + mes // 12, mes % 12 + 1
            proxima = original.replace(year=ano, month=mes, day=min(original.day, calendar.monthrange(ano, mes)[1]))
        else:
            proxima = original + timedelta(days=indice * (7 if frequencia == "semanal" else 1))
        if proxima.date() > ate:
            break
        datas.append(proxima)
    return datas


@transaction.atomic
def salvar_recorrencias(objeto, frequencia, ate):
    campo = "prazo" if isinstance(objeto, Atividade) else "inicio"
    original = timezone.localtime(getattr(objeto, campo))
    datas = datas_recorrencia(original, frequencia, ate)
    objeto.serie_id = uuid.uuid4() if frequencia else None
    if isinstance(objeto, Compromisso):
        objeto.regra_recorrencia = f"{frequencia}:{ate}" if frequencia else ""
    else:
        objeto.frequencia, objeto.repetir_ate = frequencia, ate if frequencia else None
    objeto.save()
    for proxima in datas[1:]:
        valores = {f.attname: getattr(objeto, f.attname) for f in objeto._meta.concrete_fields if not f.primary_key}
        valores[campo] = proxima
        if isinstance(objeto, Compromisso):
            valores["fim"] = proxima + (timezone.localtime(objeto.fim) - original)
        type(objeto).objects.create(**valores)
    return len(datas)


@transaction.atomic
def atualizar_recorrencias(objeto, frequencia, ate, prazo_original, serie_original):
    datas = datas_recorrencia(timezone.localtime(objeto.prazo), frequencia, ate)
    seguintes = list(Atividade.objects.select_for_update().filter(
        usuario_id=objeto.usuario_id, serie_id=serie_original, prazo__gte=prazo_original
    ).exclude(pk=objeto.pk).order_by("prazo", "id")) if serie_original else []
    objeto.serie_id = serie_original or (uuid.uuid4() if frequencia else None)
    objeto.frequencia, objeto.repetir_ate = frequencia, ate if frequencia else None
    objeto.save()
    campos = ("titulo", "tipo", "nome_disciplina", "duracao_estimada_min", "frequencia", "repetir_ate", "serie_id")
    for indice, data in enumerate(datas[1:]):
        item = seguintes[indice] if indice < len(seguintes) else Atividade(usuario_id=objeto.usuario_id)
        for campo in campos:
            setattr(item, campo, getattr(objeto, campo))
        item.prazo = data
        novo = item.pk is None
        item.save()
        if novo:
            for etapa in objeto.subtarefas.all():
                item.subtarefas.create(titulo=etapa.titulo)
    for item in seguintes[len(datas)-1:]:
        item.excluido_em = timezone.now()
        item.save(update_fields=["excluido_em"])
    return len(datas)


def dados_periodo(usuario_id, inicio, fim):
    inferior, _ = limites(inicio)
    _, superior = limites(fim)
    tarefas = list(Atividade.objects.filter(usuario_id=usuario_id, prazo__gte=inferior, prazo__lt=superior).select_related("disciplina").order_by("prazo", "id"))
    compromissos = list(Compromisso.objects.filter(usuario_id=usuario_id, inicio__lt=superior, fim__gt=inferior).order_by("inicio", "id"))
    sessoes = list(SessaoPlanejada.objects.filter(planejamento__usuario_id=usuario_id, planejamento__status="ativo", data__range=(inicio, fim)).select_related("atividade", "planejamento").order_by("data", "id"))
    aulas = list(Aula.objects.select_related("disciplina").order_by("hora_inicio"))
    # Sessões antigas sem horário recebem o mesmo horário virtual do editor existente.
    cursores = {}
    for sessao in sessoes:
        chave = (sessao.planejamento_id, sessao.data)
        cursor = cursores.get(chave, 540)
        minuto = sessao.hora_inicio.hour * 60 + sessao.hora_inicio.minute if sessao.hora_inicio else cursor
        sessao.inicio_minuto = minuto
        sessao.horario_exibicao = f"{minuto // 60:02d}:{minuto % 60:02d}"
        cursores[chave] = max(cursor, minuto + sessao.duracao_min)
    dias = []
    for i in range((fim - inicio).days + 1):
        dia = inicio + timedelta(days=i)
        inf, sup = limites(dia)
        dias.append({"data": dia,
            "tarefas": [t for t in tarefas if timezone.localtime(t.prazo).date() == dia],
            "compromissos": [c for c in compromissos if c.inicio < sup and c.fim > inf],
            "sessoes": [s for s in sessoes if s.data == dia],
            "aulas": [a for a in aulas if a.dia_semana == dia.isoweekday()]})
    return dias


def horarios_livres(dia, *, para_reserva=False):
    inicio_dia, fim_dia = limites(dia["data"])
    ocupados = []
    for c in dia["compromissos"]:
        inicio, fim = max(c.inicio, inicio_dia), min(c.fim, fim_dia)
        ocupados.append(((inicio - inicio_dia).total_seconds() / 60, (fim - inicio_dia).total_seconds() / 60))
    for tarefa in dia["tarefas"]:
        if tarefa.status in ("concluida", "nao_concluida"):
            continue
        horario = timezone.localtime(tarefa.prazo)
        inicio = horario.hour * 60 + horario.minute
        duracao = tarefa.duracao_estimada_min or 60
        ocupados.append((inicio, inicio + max(15, duracao)))
    for a in dia["aulas"]:
        ocupados.append((a.hora_inicio.hour * 60 + a.hora_inicio.minute, a.hora_fim.hour * 60 + a.hora_fim.minute))
    for s in dia["sessoes"]:
        ocupados.append((s.inicio_minuto, s.inicio_minuto + s.duracao_min))
    # Exibir o dia completo (06h-23h); ao reservar, impedir intervalos passados.
    cursor = 360
    agora = timezone.localtime()
    if para_reserva and dia["data"] < agora.date():
        return []
    if para_reserva and dia["data"] == agora.date():
        cursor = max(cursor, ((agora.hour * 60 + agora.minute) // 15 + 1) * 15)
    livres = []
    for inicio, fim in sorted(ocupados) + [(1380, 1440)]:
        inicio, fim = min(1380, max(360, int(inicio))), min(1440, int(fim))
        if inicio - cursor >= 15:
            livres.append({"inicio": cursor, "fim": min(inicio, 1380)})
        cursor = max(cursor, fim)
        if cursor >= 1380:
            break
    for item in livres:
        item["hora"] = f'{item["inicio"] // 60:02d}:{item["inicio"] % 60:02d}'
        item["termino"] = f'{item["fim"] // 60:02d}:{item["fim"] % 60:02d}'
        inicio_reserva = item["inicio"]
        if dia["data"] == agora.date():
            inicio_reserva = max(inicio_reserva, ((agora.hour * 60 + agora.minute) // 15 + 1) * 15)
        item["reservavel"] = dia["data"] >= agora.date() and item["fim"] - inicio_reserva >= 15
        item["hora_reserva"] = f"{inicio_reserva // 60:02d}:{inicio_reserva % 60:02d}"
        item["duracao"] = min(60, item["fim"] - inicio_reserva) if item["reservavel"] else 0
    return livres


def escapar_ics(valor):
    return str(valor).replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def dobrar_ics(linha):
    partes, atual = [], ""
    for caractere in linha:
        if len((atual + caractere).encode("utf-8")) > 75:
            partes.append(atual)
            atual = " "
        atual += caractere
    partes.append(atual)
    return "\r\n".join(partes)
