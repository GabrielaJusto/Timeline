
from datetime import datetime, time, timedelta

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .forms import AtividadeForm
from .models import (
    Atividade,
    Aula,
    Planejamento,
    SessaoPlanejada,
    PropostaReagendamento,
)
from .planej import (
    calcular_prioridade,
    ordenar_atividades,
    distribuir_tempo,
    gerar_proposta_reagendamento,
    calcular_tempo_restante,
)

from django.shortcuts import render
from .models import Atividade
from django.shortcuts import redirect, get_object_or_404
from .forms import AtividadeForm
from datetime import datetime, time
from .forms import CompromissoForm
from .models import Atividade, Compromisso, Disciplina 

# ==========================================
# PÁGINA HOJE
# ==========================================

def hoje(request):
    atividades = Atividade.objects.exclude(status="concluida").order_by("prazo")

    data_atual = timezone.localdate()
    inicio_semana = data_atual - timedelta(days=data_atual.weekday())

    dias_semana = [
        inicio_semana + timedelta(days=i)
        for i in range(7)
    ]

    fim_semana = dias_semana[-1]

    total_atividades = Atividade.objects.count()
    concluidas = Atividade.objects.filter(status="concluida").count()
    pendentes = Atividade.objects.exclude(status="concluida").count()

    return render(request, "hoje.html", {
        "atividades": atividades,
        "total_atividades": total_atividades,
        "concluidas": concluidas,
        "pendentes": pendentes,
        "data_atual": data_atual,
        "inicio_semana": inicio_semana,
        "fim_semana": fim_semana,
        "dias_semana": dias_semana,
    })


# ==========================================
# ADICIONAR TAREFA
# ==========================================

def adicionar_tarefa(request):
    if request.method == "POST":
        form = AtividadeForm(request.POST)

        if form.is_valid():
            atividade = form.save(commit=False)

            data = form.cleaned_data["data_entrega"]
            horario = form.cleaned_data["horario"]

            if horario is None:
                horario = time(23, 59)

            prazo = datetime.combine(data, horario)
            atividade.prazo = timezone.make_aware(prazo)

            atividade.usuario_id = 1  # Provisório para testes

            nome_disciplina = form.cleaned_data["nome_disciplina"].strip()

            atividade.nome_disciplina = nome_disciplina

            atividade.save()

            return redirect("hoje")

    else:
        form = AtividadeForm()

    atividades = Atividade.objects.all().order_by("prazo")

    total_atividades = atividades.count()
    concluidas = atividades.filter(status="concluida").count()
    pendentes = atividades.exclude(status="concluida").count()

    progresso = (
        int(concluidas / total_atividades * 100)
        if total_atividades > 0
        else 0
    )

    data_atual = timezone.localdate()
    inicio_semana = data_atual - timedelta(days=data_atual.weekday())

    dias_semana = [
        inicio_semana + timedelta(days=i)
        for i in range(7)
    ]

    fim_semana = dias_semana[-1]

    return render(request, "adicionar-tarefa.html", {
        "form": form,
        "data_atual": data_atual,
        "inicio_semana": inicio_semana,
        "fim_semana": fim_semana,
        "dias_semana": dias_semana,
        "atividades": atividades,
        "total_atividades": total_atividades,
        "concluidas": concluidas,
        "pendentes": pendentes,
    })


# ==========================================
# PÁGINA INICIAL
# ==========================================

def inicio(request):
    return hoje(request)


# ==========================================
# AGENDA
# ==========================================

def agenda(request):
    aulas = (
        Aula.objects
        .select_related("disciplina")
        .all()
        .order_by("dia_semana", "hora_inicio")
    )
 
    # Identificar o dia da semana atual
    data_atual = timezone.localdate()
    dia_atual = data_atual.isoweekday()

    # Buscar somente as aulas de hoje
    aulas_hoje = aulas.filter(dia_semana=dia_atual)

    # Buscar os compromissos cadastrados para hoje
    compromissos_hoje = (
        Compromisso.objects
        .filter(inicio__date=data_atual)
        .order_by("inicio")
)

    # Buscar as tarefas cadastradas
    atividades = Atividade.objects.all()

    # Buscar as tarefas que ainda não foram concluídas
    tarefas_pendentes = atividades.exclude(status="concluida").order_by("prazo")[:5]

    # Calcular o progresso real
    total_tarefas = atividades.count()
    tarefas_concluidas = atividades.filter(status="concluida").count()
 # Calcular a porcentagem
    if total_tarefas > 0:
        percentual_tarefas = round(
            (tarefas_concluidas / total_tarefas) * 100
        )
    else:
        percentual_tarefas = 0

    return render(request, "agenda.html", {
        "aulas": aulas_hoje,
        "compromissos": compromissos_hoje,
        "total_tarefas": total_tarefas,
        "tarefas_concluidas": tarefas_concluidas,
        "percentual_tarefas": percentual_tarefas,
        "tarefas_pendentes": tarefas_pendentes,
    })


# ==========================================
# PLANEJAMENTO INTELIGENTE
# ==========================================

def planejamento(request):
    usuario_id = 1  # Provisório para testes

    # Busca as atividades do usuário.
    atividades = Atividade.objects.filter(
        usuario_id=usuario_id
    )

    # Calcula a prioridade das atividades.
    atividades_ordenadas = ordenar_atividades(atividades)

    prioridades = [
        {
            "atividade": atividade,
            "score": calcular_prioridade(atividade),
        }
        for atividade in atividades_ordenadas
    ]

    # Define a semana atual.
    hoje = timezone.localdate()
    # REFORMULACAO_SPRINT9: semana selecionavel, sempre iniciando segunda.
    from datetime import date
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    try:
        semana_solicitada = date.fromisoformat(request.GET.get('semana', '') or request.POST.get('semana', ''))
        segunda = semana_solicitada - timedelta(days=semana_solicitada.weekday())
        if segunda < segunda_atual:
            segunda = segunda_atual
    except (ValueError, TypeError):
        segunda = segunda_atual
    domingo = segunda + timedelta(days=6)
   # Recebe as horas disponíveis do formulário.
    valores_padrao = [4, 3, 4, 3, 4, 6, 2]
    horas_por_dia = []

    for i, valor_padrao in enumerate(valores_padrao):
        valor = request.GET.get(
            f"horas_{i}",
            valor_padrao
        )

        try:
            horas = float(valor)
            horas = max(0, min(24, horas))
        except (ValueError, TypeError):
            horas = valor_padrao

        horas_por_dia.append(horas)

    # Impede alocação em dias que já passaram.
    disponibilidade = {
        (segunda + timedelta(days=i)).isoformat(): (
            horas
            if segunda + timedelta(days=i) >= hoje
            else 0
        )
        for i, horas in enumerate(horas_por_dia)
    }

    
    # Gera uma sugestão de planejamento
    sessoes = distribuir_tempo(
        atividades_ordenadas,
        disponibilidade
    )

    # Se já existe um planejamento salvo, mostra as sessões reais
    planejamento_salvo = Planejamento.objects.filter(
        usuario_id=usuario_id,
        semana_inicio=segunda,
        semana_fim=domingo,
        status="ativo"
    ).first()

    # Um plano já salvo é a fonte da verdade: aceitar novamente não pode
    # apagar as sessões de um reagendamento previamente confirmado.
    mensagem = None
    if request.method == "POST" and request.POST.get("acao") == "aceitar":
        # O POST confirma exatamente a proposta visualizada no GET.
        # A disponibilidade vai em campos ocultos, sem alterar planos existentes.
        for i, padrao in enumerate(valores_padrao):
            try:
                horas_por_dia[i] = max(0, min(24, float(request.POST.get(f'horas_{i}', padrao))))
            except (ValueError, TypeError):
                horas_por_dia[i] = padrao
        disponibilidade = {
            (segunda + timedelta(days=i)).isoformat(): (horas if segunda + timedelta(days=i) >= hoje else 0)
            for i, horas in enumerate(horas_por_dia)
        }
        sessoes = distribuir_tempo(atividades_ordenadas, disponibilidade)
        with transaction.atomic():
            plano_existente = Planejamento.objects.select_for_update().filter(
                usuario_id=usuario_id,
                semana_inicio=segunda,
                semana_fim=domingo,
                status="ativo",
            ).first()
            if plano_existente:
                mensagem = "Planejamento já salvo; sessões preservadas."
            else:
                plano_existente = Planejamento.objects.create(
                    usuario_id=usuario_id,
                    semana_inicio=segunda,
                    semana_fim=domingo,
                    status="ativo",
                    horas_disponiveis=sum(horas_por_dia),
                    horas_alocadas=sum(s["duracao_min"] for s in sessoes) / 60,
                    disponibilidade_diaria={
                        (segunda + timedelta(days=i)).isoformat(): horas
                        for i, horas in enumerate(horas_por_dia)
                    },
                )
                SessaoPlanejada.objects.bulk_create([
                    SessaoPlanejada(
                        planejamento=plano_existente,
                        atividade_id=s["atividade_id"],
                        data=s["dia"],
                        duracao_min=s["duracao_min"],
                    ) for s in sessoes
                ])
                mensagem = "Planejamento aceito e salvo com sucesso!"

    # Só exibe uma nova simulação quando o usuário informa horas no GET.
    # Em acessos normais, sempre mostra as sessões realmente persistidas.
    if planejamento_salvo and not any(
        chave.startswith("horas_") for chave in request.GET
    ) and request.method != 'POST':
        sessoes = [
            {
                "atividade_id": sessao.atividade_id,
                "atividade": sessao.atividade.titulo,
                "dia": sessao.data.isoformat(),
                "duracao_min": sessao.duracao_min,
                "prioridade": calcular_prioridade(sessao.atividade),
            }
            for sessao in planejamento_salvo.sessoes.select_related("atividade")
        ]

    # ======================================
    # CALENDÁRIO SEMANAL
    # ======================================

    dias_semana = []

    nomes_dias = [
        "Segunda",
        "Terça",
        "Quarta",
        "Quinta",
        "Sexta",
        "Sábado",
        "Domingo",
    ]

    for i, nome in enumerate(nomes_dias):
        data = segunda + timedelta(days=i)

        sessoes_do_dia = [
            sessao
            for sessao in sessoes
            if sessao["dia"] == data.isoformat()
        ]

        dias_semana.append({
            "nome": nome,
            "data": data,
            "sessoes": sessoes_do_dia,
        })

    # ======================================
    # RESUMO AUTOMÁTICO
    # ======================================

    atividades_semana = [
        atividade
        for atividade in atividades_ordenadas
        if segunda <= timezone.localtime(
            atividade.prazo
        ).date() <= domingo
    ]

    total_atividades = len(atividades_semana)


    total_minutos = sum(
        atividade.duracao_estimada_min or 60
        for atividade in atividades_semana
    )

    total_horas = round(
        total_minutos / 60,
        1
    )


    disciplinas = {
        atividade.disciplina_id
        for atividade in atividades_semana
        if atividade.disciplina_id is not None
    }

    # Alerta: compara o trabalho restante da semana com as horas disponiveis.
    # Desconsidera tarefas concluidas e tempo ja realizado.
    minutos_pendentes = sum(
        calcular_tempo_restante(atividade)
        for atividade in atividades_semana
    )
    # Se ja existe plano salvo, usa sua disponibilidade; em uma nova
    # simulacao usa os valores informados pelo usuario no formulario.
    simulando = any(chave.startswith("horas_") for chave in request.GET)
    if planejamento_salvo and not simulando and planejamento_salvo.disponibilidade_diaria:
        capacidade_minutos = sum(
            max(0, int(float(horas) * 60))
            for dia, horas in planejamento_salvo.disponibilidade_diaria.items()
            if dia >= hoje.isoformat()
        )
    else:
        capacidade_minutos = sum(int(horas * 60) for horas in disponibilidade.values())
    deficit_minutos = max(0, minutos_pendentes - capacidade_minutos)
    alerta_sobrecarga = deficit_minutos > 0
    horas_pendentes = round(minutos_pendentes / 60, 1)
    horas_disponiveis = round(capacidade_minutos / 60, 1)
    horas_excedentes = round(deficit_minutos / 60, 1)

    total_disciplinas = len(disciplinas)

    prazos_importantes = sum(
        1
        for atividade in atividades_semana
        if 0 <= (
            timezone.localtime(
                atividade.prazo
            ).date() - hoje
        ).days <= 3
    )

    # ======================================
    # ENVIA OS DADOS PARA O HTML
    # ======================================

 
    # Mensagens geradas ao marcar uma tarefa como não concluída.
    from django.contrib import messages as django_messages
    avisos = [str(aviso) for aviso in django_messages.get_messages(request)]
    if avisos:
        mensagem = " ".join(avisos)

    # Busca as propostas de reagendamento pendentes
    propostas_pendentes = PropostaReagendamento.objects.filter(
        planejamento__usuario_id=usuario_id,
        planejamento__semana_inicio=segunda,
        status="pendente"
    ).order_by("-criada_em")

    contexto = {
        "prioridades": prioridades,
        "dias_semana": dias_semana,
        "semana_inicio": segunda,
        "semana_fim": domingo,
        "semana_iso": segunda.isoformat(),
        "proposta_em_visualizacao": any(k.startswith('horas_') for k in request.GET),
        "planejamento_ja_salvo": bool(planejamento_salvo),
        "total_atividades": total_atividades,
        "total_horas": total_horas,
        "alerta_sobrecarga": alerta_sobrecarga,
        "horas_pendentes": horas_pendentes,
        "horas_disponiveis": horas_disponiveis,
        "horas_excedentes": horas_excedentes,
        "total_disciplinas": total_disciplinas,
        "prazos_importantes": prazos_importantes,
        "mensagem": mensagem,
        "propostas_pendentes": propostas_pendentes,
    }

    return render(
        request,
        "planejamento.html",
        contexto
    )

def agenda_semanal(request):
    from .models import Aula, Compromisso

    data_atual = timezone.localdate()
    inicio_semana = data_atual - timedelta(days=data_atual.weekday())
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    dias = []

    for i, data in enumerate(dias_semana, start=1):
        aulas_do_dia = Aula.objects.filter(
            dia_semana=i
        ).select_related("disciplina").order_by("hora_inicio")

        compromissos_do_dia = Compromisso.objects.filter(
            inicio__date=data
        ).order_by("inicio")

        dias.append({
            "data": data,
            "aulas": aulas_do_dia,
            "compromissos": compromissos_do_dia,
        })


    fim_semana = dias_semana[-1]

    aulas = Aula.objects.select_related("disciplina").all().order_by(
        "dia_semana", "hora_inicio"
    )

    return render(request, "agenda-semana.html", {
        "aulas": aulas,
        "data_atual": data_atual,
        "inicio_semana": inicio_semana,
        "fim_semana": fim_semana,
        "dias_semana": dias_semana,
        "dias": dias,
    })

def novo_compromisso(request):
    if request.method == "POST":
        form = CompromissoForm(request.POST)
        if form.is_valid():
            compromisso = form.save(commit=False)
            compromisso.usuario_id = 1  # Provisório para testes
            compromisso.save()
            return redirect("agenda_semana")
    else:
        form = CompromissoForm()

    return render(request, "novo-compromisso.html", {"form": form})

def excluir_compromisso(request, compromisso_id):
    compromisso = get_object_or_404(
        Compromisso,
        id=compromisso_id,
        usuario_id=1
    )

    if request.method == "POST":
        compromisso.delete()
        return redirect("agenda_semana")

    return redirect("agenda_semana")

def progresso(request):
    atividades = Atividade.objects.filter(usuario_id=1)

    total = atividades.count()
    
    concluidas = atividades.filter(
        status="concluida"
    ).count()

    percentual = round(
        (concluidas / total) * 100
    ) if total > 0 else 0

    return render(request, "progresso.html", {
        "total": total,
        "concluidas": concluidas,
        "percentual": percentual,
        "por_disciplina": [],
    })

def configuracoes(request):
    return render(request, "configuracoes.html")


def tarefas(request):
    atividades = Atividade.objects.all().order_by("prazo")

    pendentes = atividades.exclude(status="concluida").count()
    concluidas = atividades.filter(status="concluida").count()

    return render(request, "tarefas.html", {
        "atividades": atividades,
        "pendentes": pendentes,
        "concluidas": concluidas,
    })


@require_POST

def alternar_status_tarefa(request, atividade_id):
    atividade = get_object_or_404(Atividade, id=atividade_id)

    if atividade.status == "concluida":
        atividade.status = "planejada"
    else:
        atividade.status = "concluida"

    atividade.save(update_fields=["status"])

    return redirect("tarefas")


@require_POST
def marcar_atividade_nao_concluida(request, atividade_id):
    from django.contrib import messages

    atividade = get_object_or_404(Atividade, id=atividade_id, usuario_id=1)
    atividade.status = "nao_concluida"
    atividade.save(update_fields=["status"])

    hoje = timezone.localdate()
    planejamento_atual = (
        Planejamento.objects.filter(
            usuario_id=atividade.usuario_id,
            semana_inicio__lte=hoje,
            semana_fim__gte=hoje,
            status="ativo",
        ).order_by("-versao", "-id").first()
    )
    if planejamento_atual:
        atividades = list(Atividade.objects.filter(usuario_id=atividade.usuario_id))
        sessoes = gerar_proposta_reagendamento(planejamento_atual, atividades)
        if sessoes is not None:
            PropostaReagendamento.objects.filter(
                planejamento=planejamento_atual, status="pendente"
            ).update(status="rejeitada")
            PropostaReagendamento.objects.create(
                planejamento=planejamento_atual, sessoes_propostas=sessoes
            )
            messages.info(request, "Nova proposta de reagendamento disponível em Planejamento.")
        else:
            messages.warning(request, "Atividade marcada como não concluída. Não foi possível gerar uma proposta: confira a disponibilidade diária e o prazo.")
    else:
        messages.warning(request, "Atividade marcada como não concluída, mas não há planejamento ativo para esta semana.")
    return redirect("planejamento")


def notificacoes(request):
    return render(request, "notificacoes.html")

@require_POST
def rejeitar_proposta_reagendamento(request, proposta_id):
    """
    Rejeita uma proposta sem alterar
    o planejamento original.
    """

    proposta = get_object_or_404(
        PropostaReagendamento,
        id=proposta_id,
        planejamento__usuario_id=1,
        status="pendente"
    )

    proposta.status = "rejeitada"
    proposta.save(update_fields=["status"])

    return redirect("planejamento")

@require_POST
def aceitar_proposta_reagendamento(request, proposta_id):
    """
    Aceita uma proposta e atualiza o planejamento
    somente após a confirmação do estudante.
    """

    with transaction.atomic():
        proposta = get_object_or_404(
            PropostaReagendamento.objects.select_for_update(),
            id=proposta_id,
            planejamento__usuario_id=1,
            status="pendente"
        )

        planejamento = proposta.planejamento
        novas_sessoes = proposta.sessoes_propostas

        # Valida todas as sessões antes de alterar o plano.
        sessoes_validadas = []

        for sessao in novas_sessoes:
            atividade = get_object_or_404(
                Atividade,
                id=sessao["atividade_id"],
                usuario_id=planejamento.usuario_id
            )

            data = datetime.fromisoformat(
                sessao["dia"]
            ).date()

            duracao = int(sessao["duracao_min"])

            if (
                duracao <= 0
                or not (
                    planejamento.semana_inicio
                    <= data
                    <= planejamento.semana_fim
                )
            ):
                raise ValueError(
                    "A proposta contém uma sessão inválida."
                )


            sessoes_validadas.append(
                SessaoPlanejada(
                    planejamento=planejamento,
                    atividade=atividade,
                    data=data,
                    duracao_min=duracao
                )
            )

        # Só modifica o planejamento após validar tudo.
        planejamento.sessoes.all().delete()

        SessaoPlanejada.objects.bulk_create(
            sessoes_validadas
        )

        planejamento.horas_alocadas = (
            sum(s.duracao_min for s in sessoes_validadas) / 60
        )
        planejamento.save(update_fields=["horas_alocadas"])

        PropostaReagendamento.objects.filter(
            planejamento=planejamento, status="pendente"
        ).exclude(id=proposta.id).update(status="rejeitada")
        proposta.status = "aceita"
        proposta.save(update_fields=["status"])

    return redirect("planejamento")
