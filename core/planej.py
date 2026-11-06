from datetime import date, timedelta
from django.utils import timezone


def calcular_prioridade(atividade):
    agora = timezone.now()
    if atividade.prazo is None:
        dias_restantes = float('inf')
    else:
        dias_restantes = (atividade.prazo - agora).total_seconds() / 86400
    if dias_restantes <= 1:
        urgencia = 10
    elif dias_restantes <= 3:
        urgencia = 8
    elif dias_restantes <= 7:
        urgencia = 6
    elif dias_restantes <= 14:
        urgencia = 4
    else:
        urgencia = 2
    importancia = max(1, min(5, atividade.importancia or 3)) * 2
    dificuldade = max(1, min(5, atividade.dificuldade or 3)) * 2
    peso = max(0, min(100, float(atividade.peso_nota or 0))) / 10
    return round(urgencia * .40 + importancia * .30 + dificuldade * .15 + peso * .15, 2)


def ordenar_atividades(atividades):
    return sorted((a for a in atividades if a.status != 'concluida'), key=calcular_prioridade, reverse=True)


def calcular_tempo_restante(atividade):
    if atividade.status == 'concluida':
        return 0
    estimado = atividade.duracao_estimada_min or 60
    realizado = atividade.duracao_real_min or 0
    return max(0, estimado - realizado)


def distribuir_tempo(atividades, disponibilidade):
    minutos = {dia: max(0, int(float(horas) * 60)) for dia, horas in disponibilidade.items()}
    sessoes = []
    for atividade in ordenar_atividades(atividades):
        restante = calcular_tempo_restante(atividade)
        for dia in sorted(minutos):
            if restante <= 0:
                break
            if atividade.prazo and date.fromisoformat(dia) > timezone.localtime(atividade.prazo).date():
                continue
            livre = minutos[dia]
            if livre <= 0 or (not atividade.fragmentavel and livre < restante):
                continue
            duracao = min(livre, restante) if atividade.fragmentavel else restante
            sessoes.append({'atividade_id': atividade.id, 'atividade': atividade.titulo,
                            'dia': dia, 'duracao_min': duracao,
                            'prioridade': calcular_prioridade(atividade)})
            minutos[dia] -= duracao
            restante -= duracao
    return sessoes


def identificar_sessoes_pendentes(planejamento):
    return [s for s in planejamento.sessoes.select_related('atividade')
            if s.atividade.status in ('nao_concluida', 'atrasada')]


def calcular_disponibilidade_restante(planejamento, disponibilidade):
    minutos = {dia: max(0, int(float(horas) * 60)) for dia, horas in disponibilidade.items()}
    for sessao in planejamento.sessoes.all():
        dia = sessao.data.isoformat()
        if dia in minutos:
            minutos[dia] = max(0, minutos[dia] - sessao.duracao_min)
    return minutos


def gerar_proposta_reagendamento(planejamento, atividades, disponibilidade=None):
    """Propõe nova lista COMPLETA de sessões sem alterar o banco.

    Somente atividades explicitamente não concluídas/atrasadas são movidas.
    Sessões de outras atividades são preservadas. Sem capacidade, retorna None.
    """
    disponibilidade = disponibilidade if disponibilidade is not None else planejamento.disponibilidade_diaria
    if not disponibilidade:
        return None
    hoje = timezone.localdate()
    sessoes_originais = list(planejamento.sessoes.select_related('atividade').order_by('data', 'id'))
    ids_pendentes = {a.id for a in atividades if a.status in ('nao_concluida', 'atrasada')}
    if not ids_pendentes or not any(s.atividade_id in ids_pendentes for s in sessoes_originais):
        return None
    preservadas = [s for s in sessoes_originais if s.atividade_id not in ids_pendentes]
    minutos = {dia: max(0, int(float(horas) * 60)) for dia, horas in disponibilidade.items()}
    for sessao in preservadas:
        dia = sessao.data.isoformat()
        if dia in minutos:
            minutos[dia] -= sessao.duracao_min
    if any(v < 0 for v in minutos.values()):
        return None
    proposta = [{'atividade_id': s.atividade_id, 'dia': s.data.isoformat(),
                 'duracao_min': s.duracao_min} for s in preservadas]
    pendentes = ordenar_atividades([a for a in atividades if a.id in ids_pendentes])
    for atividade in pendentes:
        sessoes_anteriores = [s for s in sessoes_originais if s.atividade_id == atividade.id]
        if not sessoes_anteriores:
            continue
        restante = calcular_tempo_restante(atividade)
        if restante == 0:
            continue
        ultima_data = max(s.data for s in sessoes_anteriores)
        limite = timezone.localtime(atividade.prazo).date() if atividade.prazo else planejamento.semana_fim
        # Reagendar somente para depois da sessão perdida, nunca para o passado.
        dias = [dia for dia in sorted(minutos)
                if max(hoje, ultima_data + timedelta(days=1)) <= date.fromisoformat(dia)
                <= min(limite, planejamento.semana_fim)]
        alocadas = []
        for dia in dias:
            if restante <= 0:
                break
            livre = minutos[dia]
            if livre <= 0 or (not atividade.fragmentavel and livre < restante):
                continue
            duracao = min(livre, restante) if atividade.fragmentavel else restante
            alocadas.append({'atividade_id': atividade.id, 'dia': dia, 'duracao_min': duracao})
            minutos[dia] -= duracao
            restante -= duracao
        if restante:
            return None
        proposta.extend(alocadas)
    proposta.sort(key=lambda s: (s['dia'], s['atividade_id']))

    original = sorted(
        [
            {
                'atividade_id': s.atividade_id,
                'dia': s.data.isoformat(),
                'duracao_min': s.duracao_min,
            }
            for s in planejamento.sessoes.all()
        ],
        key=lambda s: (s['dia'], s['atividade_id'])
    )

    return proposta if proposta != original else None
