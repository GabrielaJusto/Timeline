
from datetime import date,datetime, time, timedelta
from urllib import request

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm

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
)

from django.shortcuts import render
from .models import Atividade
from django.shortcuts import redirect, get_object_or_404
from .forms import AtividadeForm
from datetime import datetime, time
from .forms import CompromissoForm
from .models import Atividade, Compromisso, Disciplina


def pagina_login(request):
    if request.user.is_authenticated:
        return redirect("hoje")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        usuario = authenticate(
            request,
            username=username,
            password=password
        )

        if usuario is not None:
            login(request, usuario)
            return redirect("hoje")

        return render(
            request,
            "login.html",
            {"erro": "Usuário ou senha incorretos."}
        )

    return render(request, "login.html")

def pagina_cadastro(request):
    if request.user.is_authenticated:
        return redirect("hoje")

    if request.method == "POST":
        formulario = UserCreationForm(request.POST)

        if formulario.is_valid():
            usuario = formulario.save()
            login(request, usuario)
            return redirect("hoje")
    else:
        formulario = UserCreationForm()

    return render(
        request,
        "cadastro.html",
        {"formulario": formulario}
    )

@require_POST
def pagina_logout(request):
    logout(request)
    return redirect("login")


# ==========================================
# PÃGINA HOJE
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

            atividade.usuario_id = 1  # ProvisÃ³rio para testes

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
# PÃGINA INICIAL
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

    # Buscar as tarefas que ainda nÃ£o foram concluÃ­das
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
    usuario_id = 1  # ProvisÃ³rio para testes

    # Busca as atividades do usuÃ¡rio.
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
   # Recebe as horas disponÃ­veis do formulÃ¡rio.
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

    # Impede alocaÃ§Ã£o em dias que jÃ¡ passaram.
    disponibilidade = {
        (segunda + timedelta(days=i)).isoformat(): (
            horas
            if segunda + timedelta(days=i) >= hoje
            else 0
        )
        for i, horas in enumerate(horas_por_dia)
    }


    # Gera uma sugestÃ£o de planejamento
    sessoes = distribuir_tempo(
        atividades_ordenadas,
        disponibilidade
    )

    # Se jÃ¡ existe um planejamento salvo, mostra as sessÃµes reais
    planejamento_salvo = Planejamento.objects.filter(
        usuario_id=usuario_id,
        semana_inicio=segunda,
        semana_fim=domingo,
        status="ativo"
    ).first()

    # Um plano jÃ¡ salvo Ã© a fonte da verdade: aceitar novamente nÃ£o pode
    # apagar as sessÃµes de um reagendamento previamente confirmado.
    mensagem = None
    if request.method == "POST" and request.POST.get("acao") == "aceitar":
        with transaction.atomic():
            plano_existente = Planejamento.objects.select_for_update().filter(
                usuario_id=usuario_id,
                semana_inicio=segunda,
                semana_fim=domingo,
                status="ativo",
            ).first()
            if plano_existente:
                mensagem = "Planejamento jÃ¡ salvo; sessÃµes preservadas."
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

    # SÃ³ exibe uma nova simulaÃ§Ã£o quando o usuÃ¡rio informa horas no GET.
    # Em acessos normais, sempre mostra as sessÃµes realmente persistidas.
    if planejamento_salvo and not any(
        chave.startswith("horas_") for chave in request.GET
    ):
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
    # CALENDÃRIO SEMANAL
    # ======================================

    dias_semana = []

    nomes_dias = [
        "Segunda",
        "TerÃ§a",
        "Quarta",
        "Quinta",
        "Sexta",
        "SÃ¡bado",
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
    # RESUMO AUTOMÃTICO
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


    # Mensagens geradas ao marcar uma tarefa como nÃ£o concluÃ­da.
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
        "total_atividades": total_atividades,
        "total_horas": total_horas,
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

    semana_parametro = request.GET.get("semana")

    if semana_parametro:
        try:
            data_referencia = date.fromisoformat(semana_parametro)
        except ValueError:
            data_referencia = data_atual
    else:
        data_referencia = data_atual

    inicio_semana = data_referencia - timedelta(days=data_referencia.weekday())
    semana_anterior = inicio_semana - timedelta(days=7)
    semana_seguinte = inicio_semana + timedelta(days=7)
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
    titulo_semana = (
    f"{inicio_semana.strftime('%d/%m')} a "
    f"{fim_semana.strftime('%d/%m/%Y')}"
)

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
        "semana_anterior": semana_anterior,
        "semana_seguinte": semana_seguinte,
        "titulo_semana": titulo_semana,
    })

def novo_compromisso(request):
    if request.method == "POST":
        form = CompromissoForm(request.POST)
        if form.is_valid():
            compromisso = form.save(commit=False)
            compromisso.usuario_id = 1  # ProvisÃ³rio para testes
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
    from django.db.models import Q

    atividades = Atividade.objects.all()

    busca = request.GET.get("busca", "").strip()
    status = request.GET.get("status", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    ordem = request.GET.get("ordem", "prazo")

    if busca:
        atividades = atividades.filter(
            Q(titulo__icontains=busca) |
            Q(nome_disciplina__icontains=busca) |
            Q(disciplina__nome__icontains=busca)
        ).distinct()

    status_validos = {item[0] for item in Atividade.STATUS}
    tipos_validos = {item[0] for item in Atividade.TIPOS}

    if status in status_validos:
        atividades = atividades.filter(status=status)

    if tipo in tipos_validos:
        atividades = atividades.filter(tipo=tipo)

    if ordem == "prazo_desc":
        atividades = atividades.order_by("-prazo", "id")
    elif ordem == "titulo":
        atividades = atividades.order_by("titulo", "id")
    else:
        atividades = atividades.order_by("prazo", "id")

    return render(request, "tarefas.html", {
        "atividades": atividades,
        "pendentes": atividades.exclude(status="concluida").count(),
        "concluidas": atividades.filter(status="concluida").count(),
        "busca": busca,
        "status_selecionado": status,
        "tipo_selecionado": tipo,
        "ordem_selecionada": ordem,
        "opcoes_status": Atividade.STATUS,
        "opcoes_tipo": Atividade.TIPOS,
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
            messages.info(request, "Nova proposta de reagendamento disponÃ­vel em Planejamento.")
        else:
            messages.warning(request, "Atividade marcada como nÃ£o concluÃ­da. NÃ£o foi possÃ­vel gerar uma proposta: confira a disponibilidade diÃ¡ria e o prazo.")
    else:
        messages.warning(request, "Atividade marcada como nÃ£o concluÃ­da, mas nÃ£o hÃ¡ planejamento ativo para esta semana.")
    return redirect("planejamento")


def notificacoes(request):
    return render(request, "notificacoes.html")

import calendar

def agenda_mensal(request):
    hoje = timezone.localdate()

    mes_parametro = request.GET.get("mes")

    try:
        data_referencia = (
            date.fromisoformat(mes_parametro)
            if mes_parametro else hoje
        )
    except ValueError:
        data_referencia = hoje

    primeiro_dia = data_referencia.replace(day=1)

    if primeiro_dia.month == 12:
        proximo_mes = primeiro_dia.replace(
            year=primeiro_dia.year + 1, month=1
        )
    else:
        proximo_mes = primeiro_dia.replace(
            month=primeiro_dia.month + 1
        )

    mes_anterior = primeiro_dia - timedelta(days=1)
    ultimo_dia = proximo_mes - timedelta(days=1)


    calendario = calendar.Calendar(firstweekday=0)
    semanas = calendario.monthdatescalendar(
        primeiro_dia.year, primeiro_dia.month
    )

    compromissos = Compromisso.objects.filter(
        inicio__date__range=(primeiro_dia, ultimo_dia)
    )

    compromissos_por_dia = {}

    for compromisso in compromissos:
        data_compromisso = timezone.localtime(compromisso.inicio).date()

        compromissos_por_dia.setdefault(
            data_compromisso, []
        ).append(compromisso)

    semanas_calendario = []

    for semana in semanas:
        dias = []
        for dia in semana:
            dias.append({
                "data": dia,
                "mes_atual": dia.month == primeiro_dia.month,
                "hoje": dia == hoje,
                "compromissos": compromissos_por_dia.get(dia, []),
            })
        semanas_calendario.append(dias)

    meses = [
        "janeiro", "fevereiro", "marÃ§o", "abril",
        "maio", "junho", "julho", "agosto",
        "setembro", "outubro", "novembro", "dezembro"
    ]

    return render(request, "agenda-mes.html", {
        "semanas": semanas_calendario,
        "titulo_mes": (
            f"{meses[primeiro_dia.month - 1].capitalize()} "
            f"{primeiro_dia.year}"
        ),
        "mes_anterior": mes_anterior,
        "proximo_mes": proximo_mes,
    })

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
    somente apÃ³s a confirmaÃ§Ã£o do estudante.
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

        # Valida todas as sessÃµes antes de alterar o plano.
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
                    "A proposta contÃ©m uma sessÃ£o invÃ¡lida."
                )


            sessoes_validadas.append(
                SessaoPlanejada(
                    planejamento=planejamento,
                    atividade=atividade,
                    data=data,
                    duracao_min=duracao
                )
            )

        # SÃ³ modifica o planejamento apÃ³s validar tudo.
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
