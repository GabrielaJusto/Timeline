
from datetime import date, timedelta
from django.utils import timezone


def calcular_prioridade(atividade):
    """
    Calcula a prioridade de uma atividade considerando:
    - proximidade do prazo
    - importância
    - dificuldade
    - peso na nota
    """

    agora = timezone.now()

    # Calcula quantos dias faltam até o prazo.
    tempo_restante = atividade.prazo - agora
    dias_restantes = tempo_restante.total_seconds() / 86400

    # Urgência: quanto mais próximo o prazo, maior a pontuação.
    if dias_restantes < 0:
        urgencia = 10
    elif dias_restantes <= 1:
        urgencia = 10
    elif dias_restantes <= 3:
        urgencia = 8
    elif dias_restantes <= 7:
        urgencia = 6
    elif dias_restantes <= 14:
        urgencia = 4
    else:
        urgencia = 2

    # Escala assumida: importância e dificuldade de 1 a 5.
    importancia = max(1, min(5, atividade.importancia or 3)) * 2
    dificuldade = max(1, min(5, atividade.dificuldade or 3)) * 2

    # Peso na nota: assumimos percentual de 0 a 100.
    peso = max(0, min(100, float(atividade.peso_nota or 0))) / 10

    # Pontuação final: escala aproximada de 0 a 10.
    score = (
        urgencia * 0.40
        + importancia * 0.30
        + dificuldade * 0.15
        + peso * 0.15
    )

    return round(score, 2)


def ordenar_atividades(atividades):
    """
    Retorna as atividades pendentes em ordem de prioridade.
    """

    pendentes = [
        atividade
        for atividade in atividades
        if atividade.status not in ("concluida", "nao_concluida")
    ]

    return sorted(
        pendentes,
        key=calcular_prioridade,
        reverse=True
    )


def distribuir_tempo(atividades, disponibilidade):
    """
    Distribui atividades nos dias disponíveis.

    disponibilidade:
        Dicionário com a data e as horas livres.
        Exemplo: {"2026-11-02": 3, "2026-11-03": 2}

    Retorna uma lista de sessões de estudo.
    """

    atividades_ordenadas = ordenar_atividades(atividades)

    # Converte as horas disponíveis para minutos.
    minutos_disponiveis = {
        dia: max(0, int(horas * 60))
        for dia, horas in disponibilidade.items()
    }

    planejamento = []

    for atividade in atividades_ordenadas:
        tempo_restante = max(
            0, atividade.duracao_estimada_min or 60
        )

        for dia in sorted(minutos_disponiveis):
            if tempo_restante <= 0:
                break

            # Não aloca estudo depois do prazo da atividade.
            data_estudo = date.fromisoformat(dia)
            if data_estudo > timezone.localtime(
                atividade.prazo
            ).date():
                continue

            livre = minutos_disponiveis[dia]

            if livre <= 0:
                continue

            # Atividades não fragmentáveis precisam caber
            # inteiramente em um único dia.
            if not atividade.fragmentavel:
                if livre < tempo_restante:
                    continue
                minutos_sessao = tempo_restante
            else:
                minutos_sessao = min(livre, tempo_restante)

            planejamento.append({
                "atividade_id": atividade.id,
                "atividade": atividade.titulo,
                "dia": dia,
                "duracao_min": minutos_sessao,
                "prioridade": calcular_prioridade(atividade),
            })

            minutos_disponiveis[dia] -= minutos_sessao
            tempo_restante -= minutos_sessao

    return planejamento

