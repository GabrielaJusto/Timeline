
from datetime import datetime, time, timedelta

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import AtividadeForm
from .models import (
    Atividade,
    Aula,
    Planejamento,
    SessaoPlanejada,
)
from .planej import (
    calcular_prioridade,
    ordenar_atividades,
    distribuir_tempo,
)


# ==========================================
# PÁGINA HOJE
# ==========================================

def hoje(request):
    atividades = Atividade.objects.all().order_by("prazo")

    data_atual = timezone.localdate()
    inicio_semana = data_atual - timedelta(days=data_atual.weekday())

    dias_semana = [
        inicio_semana + timedelta(days=i)
        for i in range(7)
    ]

    fim_semana = dias_semana[-1]

    total_atividades = atividades.count()
    concluidas = atividades.filter(status="concluida").count()
    pendentes = atividades.exclude(status="concluida").count()

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
    return render(request, "index.html")


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

    return render(request, "agenda.html", {
        "aulas": aulas
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
    segunda = hoje - timedelta(days=hoje.weekday())
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

    # Gera as sessões de estudo.
    sessoes = distribuir_tempo(
        atividades_ordenadas,
        disponibilidade
    )

    # ======================================
    # ACEITAR E SALVAR PLANEJAMENTO
    # ======================================

    mensagem = None

    if (
        request.method == "POST"
        and request.POST.get("acao") == "aceitar"
    ):

        # Salva o planejamento e suas sessões
        # como uma única operação no banco.
        with transaction.atomic():

            planejamento_salvo, criado = (
                Planejamento.objects.update_or_create(
                    usuario_id=usuario_id,
                    semana_inicio=segunda,
                    semana_fim=domingo,
                    status="ativo",
                    defaults={
                        "horas_disponiveis": sum(
                            horas_por_dia
                        ),
                        "horas_alocadas": sum(
                            sessao["duracao_min"]
                            for sessao in sessoes
                        ) / 60,
                    },
                )
            )

            # Remove as sessões anteriores
            # para evitar duplicações.
            planejamento_salvo.sessoes.all().delete()

            # Salva as sessões atualizadas.
            for sessao in sessoes:
                SessaoPlanejada.objects.create(
                    planejamento=planejamento_salvo,
                    atividade_id=sessao["atividade_id"],
                    data=sessao["dia"],
                    duracao_min=sessao["duracao_min"],
                )

        mensagem = (
            "Planejamento aceito e salvo com sucesso!"
        )

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

    contexto = {
        "prioridades": prioridades,
        "dias_semana": dias_semana,
        "semana_inicio": segunda,
        "semana_fim": domingo,
        "total_atividades": total_atividades,
        "total_horas": total_horas,
        "total_disciplinas": total_disciplinas,
        "prazos_importantes": prazos_importantes,
        "mensagem": mensagem,
    }

    return render(
        request,
        "planejamento.html",
        contexto
    )
