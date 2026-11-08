
from datetime import date,datetime, time, timedelta
from urllib import request

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from .auth_forms import CadastroForm

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
        formulario = CadastroForm(request.POST)

        if formulario.is_valid():
            usuario = formulario.save()
            login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("hoje")
    else:
        formulario = CadastroForm()

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

            if request.headers.get("X-Task-Modal") == "1":
                from django.http import JsonResponse
                from django.urls import reverse
                return JsonResponse({"redirect": reverse("tarefas")})
            return redirect("tarefas")
        
        # Se houver erros no formulário da página Tarefas
        if request.POST.get("origem") == "tarefas":
            return tarefas(request, formulario=form)
        
    else:
        form = AtividadeForm()

    return render(request, "adicionar-tarefa.html", {"form": form})


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

    # Buscar tarefas com prazo para hoje
    tarefas_hoje = atividades.filter(
        prazo__date=data_atual
    ).order_by("prazo")

    # Reunir tarefas, aulas e compromissos em uma única lista
    eventos_do_dia = []

    for compromisso in compromissos_hoje:
        eventos_do_dia.append({
            "horario": timezone.localtime(compromisso.inicio).time(),
            "titulo": compromisso.titulo,
            "tipo": "Compromisso",
            "detalhe": compromisso.get_categoria_display()
                if hasattr(compromisso, "get_categoria_display")
                else compromisso.categoria,
        })

    for aula in aulas_hoje:
        eventos_do_dia.append({
            "horario": aula.hora_inicio,
            "titulo": aula.disciplina.nome,
            "tipo": "Aula",
            "detalhe": aula.local or "",
        })

    for tarefa in tarefas_hoje:
        eventos_do_dia.append({
            "horario": timezone.localtime(tarefa.prazo).time(),
            "titulo": tarefa.titulo,
            "tipo": "Tarefa",
            "detalhe": tarefa.get_status_display(),
        })

    # Organizar todos os eventos pelo horário
    eventos_do_dia.sort(key=lambda evento: evento["horario"])

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
        "tarefas_hoje": tarefas_hoje,
        "total_tarefas": total_tarefas,
        "tarefas_concluidas": tarefas_concluidas,
        "percentual_tarefas": percentual_tarefas,
        "tarefas_pendentes": tarefas_pendentes,
        "eventos_do_dia": eventos_do_dia,
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
    ) and request.method != 'POST':
        sessoes = [
            {
                "atividade_id": sessao.atividade_id,
                "atividade": sessao.atividade.titulo,
                "dia": sessao.data.isoformat(),
                "duracao_min": sessao.duracao_min,
                "id": sessao.id,
                "hora_inicio": sessao.hora_inicio.strftime("%H:%M") if sessao.hora_inicio else"",                "prioridade": calcular_prioridade(sessao.atividade),
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

        tarefas_do_dia = Atividade.objects.filter(
            usuario_id=1,
            prazo__date=data
        ).order_by("prazo")

        dias.append({
            "data": data,
            "aulas": aulas_do_dia,
            "compromissos": compromissos_do_dia,
            "tarefas": tarefas_do_dia,
        })


    fim_semana = dias_semana[-1]
    titulo_semana = (
    f"{inicio_semana.strftime('%d/%m')} a "
    f"{fim_semana.strftime('%d/%m/%Y')}"
)

    aulas = Aula.objects.select_related("disciplina").all().order_by(
        "dia_semana", "hora_inicio"
    )

    # Tarefas com prazo na semana exibida no calendário
    tarefas_semana = Atividade.objects.filter(
        usuario_id=1,
        prazo__date__range=(inicio_semana, fim_semana)
    )

    tarefas_total = tarefas_semana.count()

    tarefas_concluidas = tarefas_semana.filter(
        status="concluida"
    ).count()

    tarefas_percentual = round(
        (tarefas_concluidas / tarefas_total) * 100
    ) if tarefas_total > 0 else 0

    # Contar dias organizados com pelo menos uma tarefa cadastrada
    dias_organizados = 0

    for dia in dias:
        
        tem_compromisso = dia["compromissos"].exists()
        tem_tarefa = dia["tarefas"].exists()

        if tem_tarefa or tem_compromisso:
            dias_organizados += 1

    dias_percentual = round((dias_organizados / 7) * 100)

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
        "tarefas_total": tarefas_total,
        "tarefas_concluidas": tarefas_concluidas,
        "tarefas_percentual": tarefas_percentual,
        "dias_organizados": dias_organizados,
        "dias_percentual": dias_percentual,
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


def tarefas(request, formulario=None):
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
        "form": formulario if formulario is not None else AtividadeForm(),
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

    # Buscar tarefas cadastradas no mês
    tarefas = Atividade.objects.filter(
        usuario_id=1,
        prazo__date__range=(primeiro_dia, ultimo_dia)
    ).order_by("prazo")

    # Organizar as tarefas por dia
    tarefas_por_dia = {}

    for tarefa in tarefas:
        data_tarefa = timezone.localtime(tarefa.prazo).date()

        tarefas_por_dia.setdefault(
            data_tarefa, []
        ).append(tarefa)

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
                "tarefas": tarefas_por_dia.get(dia, []),
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


# Historico de planejamentos aceitos
def historico_planejamentos(request):
    usuario_id = 1  # Mesmo usuario provisorio da tela de planejamento
    planos = (
        Planejamento.objects.filter(usuario_id=usuario_id)
        .prefetch_related("sessoes__atividade")
        .order_by("-semana_inicio", "-versao", "-gerado_em")
    )
    nomes = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    historico = []
    for plano in planos:
        sessoes_por_data = {}
        for sessao in plano.sessoes.all():
            sessoes_por_data.setdefault(sessao.data, []).append(sessao)
        dias = [
            {
                "nome": nome,
                "data": plano.semana_inicio + timedelta(days=i),
                "sessoes": sessoes_por_data.get(plano.semana_inicio + timedelta(days=i), []),
            }
            for i, nome in enumerate(nomes)
        ]
        historico.append({"plano": plano, "dias": dias})
    return render(request, "historico-planejamentos.html", {"historico": historico})
def editar_sessao_planejamento(request, sessao_id):
    """Edita sessao, detecta conflitos e oferece realocacao confirmada."""
    from datetime import date, datetime, time, timedelta
    from django.contrib import messages
    from django.db import transaction
    from django.shortcuts import get_object_or_404, redirect, render
    from django.utils import timezone

    def intervalos(plano):
        """Horarios virtuais para sessoes legadas, sem alterar dados existentes."""
        sessoes = list(plano.sessoes.select_related('atividade').order_by('data', 'id'))
        por_dia = {}
        for s in sessoes:
            por_dia.setdefault(s.data, []).append(s)
        resultado = {}
        for dia, grupo in por_dia.items():
            cursor = 9 * 60
            for s in grupo:
                if s.hora_inicio is not None:
                    inicio = s.hora_inicio.hour * 60 + s.hora_inicio.minute
                else:
                    inicio = cursor
                resultado[s.id] = (inicio, inicio + s.duracao_min)
                cursor = max(cursor, inicio + s.duracao_min)
        return resultado

    def primeiro_horario_livre(plano, duracao, excluidos, preferencia=None):
        # Sugere um horario em blocos de 30 min, das 07:00 as 23:00.
        ocupacao = intervalos(plano)
        outras = list(plano.sessoes.exclude(id__in=excluidos))
        dias = [plano.semana_inicio + timedelta(days=i) for i in range(7)]
        if preferencia in dias:
            dias = [preferencia] + [d for d in dias if d != preferencia]
        for dia in dias:
            if dia < timezone.localdate():
                continue
            for inicio in range(7 * 60, 23 * 60 - duracao + 1, 30):
                fim = inicio + duracao
                if all(o.data != dia or not (inicio < ocupacao[o.id][1] and ocupacao[o.id][0] < fim) for o in outras):
                    return dia, inicio
        return None

    def hhmm(minutos):
        return f'{minutos // 60:02d}:{minutos % 60:02d}'

    sessao = get_object_or_404(
        SessaoPlanejada.objects.select_related('planejamento', 'atividade'),
        id=sessao_id, planejamento__usuario_id=1,
    )
    plano = sessao.planejamento
    intervalo_atual = intervalos(plano)
    atual_min = intervalo_atual[sessao.id][0]
    form_data = sessao.data.isoformat()
    form_hora = hhmm(atual_min) if atual_min < 1440 else '09:00'
    conflito = None
    sugestao = None
    erro = None

    if request.method == 'POST':
        try:
            data_nova = date.fromisoformat(request.POST.get('data', ''))
            hora_nova = datetime.strptime(request.POST.get('hora_inicio', ''), '%H:%M').time()
            inicio = hora_nova.hour * 60 + hora_nova.minute
            fim = inicio + sessao.duracao_min
            if not plano.semana_inicio <= data_nova <= plano.semana_fim:
                raise ValueError('Escolha uma data dentro da semana deste planejamento.')
            if data_nova < timezone.localdate():
                raise ValueError('Nao e permitido mover uma sessao para um dia passado.')
            if fim > 1440:
                raise ValueError('A atividade deve terminar no mesmo dia.')
            form_data = data_nova.isoformat()
            form_hora = hhmm(inicio)
        except (ValueError, TypeError) as exc:
            erro = str(exc) if str(exc) and 'format' not in str(exc).lower() else 'Data ou horario invalido.'
        else:
            with transaction.atomic():
                # Bloqueia as sessoes do planejamento durante a confirmacao.
                list(SessaoPlanejada.objects.select_for_update().filter(planejamento=plano))
                ocupacao = intervalos(plano)
                sobrepostas = [o for o in plano.sessoes.select_related('atividade').exclude(id=sessao.id)
                               if o.data == data_nova and inicio < ocupacao[o.id][1] and ocupacao[o.id][0] < fim]
                if not sobrepostas:
                    sessao.data = data_nova
                    sessao.hora_inicio = hora_nova
                    sessao.save(update_fields=['data', 'hora_inicio'])
                    messages.success(request, 'Horario atualizado com sucesso.')
                    return redirect(f'/planejamento/?semana={plano.semana_inicio.isoformat()}')

                nomes = ', '.join(o.atividade.titulo for o in sobrepostas)
                conflito = f'Conflito com: {nomes}. Nenhuma alteracao foi salva.'
                # Caso haja varios conflitos, exige que o usuario escolha outro horario.
                if len(sobrepostas) > 1:
                    erro = 'Ha mais de uma atividade sobreposta. Escolha outro horario para evitar deslocar varias sessoes.'
                else:
                    outra = sobrepostas[0]
                    escolha = request.POST.get('decisao')
                    # Escolha 1: atividade editada fica no horario escolhido;
                    # atividade conflitante sera realocada.
                    if escolha == 'manter_editada':
                        sugestao_bruta = primeiro_horario_livre(plano, outra.duracao_min, {sessao.id, outra.id}, preferencia=outra.data)
                        # A sugestao nao pode colidir com o novo intervalo da editada.
                        if sugestao_bruta:
                            dia_s, min_s = sugestao_bruta
                            if dia_s == data_nova and min_s < fim and inicio < min_s + outra.duracao_min:
                                sugestao_bruta = None
                        if sugestao_bruta is None:
                            # Segunda busca considerando a sessao editada em sua nova posicao.
                            dias = [plano.semana_inicio + timedelta(days=i) for i in range(7)]
                            outras_sessoes = list(plano.sessoes.exclude(id__in=[sessao.id, outra.id]))
                            for d in ([outra.data] + [x for x in dias if x != outra.data]):
                                if d < timezone.localdate():
                                    continue
                                for m in range(420, 1380 - outra.duracao_min + 1, 30):
                                    n = m + outra.duracao_min
                                    if d == data_nova and m < fim and inicio < n:
                                        continue
                                    if all(o.data != d or not (m < ocupacao[o.id][1] and ocupacao[o.id][0] < n) for o in outras_sessoes):
                                        sugestao_bruta = (d, m)
                                        break
                                if sugestao_bruta:
                                    break
                        if sugestao_bruta:
                            d, m = sugestao_bruta
                            sugestao = {'data': d.isoformat(), 'hora': hhmm(m), 'titulo': outra.atividade.titulo}
                            if request.POST.get('confirmar') == '1' and request.POST.get('sugestao_data') == sugestao['data'] and request.POST.get('sugestao_hora') == sugestao['hora']:
                                sessao.data = data_nova
                                sessao.hora_inicio = hora_nova
                                outra.data = d
                                outra.hora_inicio = time(m // 60, m % 60)
                                sessao.save(update_fields=['data', 'hora_inicio'])
                                outra.save(update_fields=['data', 'hora_inicio'])
                                messages.success(request, 'Edicao salva e atividade conflitante realocada.')
                                return redirect(f'/planejamento/?semana={plano.semana_inicio.isoformat()}')
                        else:
                            erro = 'Nao foi encontrado horario livre para realocar a outra atividade nesta semana.'
                    elif escolha == 'manter_outra':
                        # Mantem a atividade conflitante e sugere outro horario para a editada.
                        sugestao_bruta = primeiro_horario_livre(plano, sessao.duracao_min, {sessao.id}, preferencia=data_nova)
                        if sugestao_bruta:
                            d, m = sugestao_bruta
                            sugestao = {'data': d.isoformat(), 'hora': hhmm(m), 'titulo': sessao.atividade.titulo}
                            if request.POST.get('confirmar') == '1' and request.POST.get('sugestao_data') == sugestao['data'] and request.POST.get('sugestao_hora') == sugestao['hora']:
                                sessao.data = d
                                sessao.hora_inicio = time(m // 60, m % 60)
                                sessao.save(update_fields=['data', 'hora_inicio'])
                                messages.success(request, 'Atividade realocada para o horario sugerido.')
                                return redirect(f'/planejamento/?semana={plano.semana_inicio.isoformat()}')
                        else:
                            erro = 'Nao foi encontrado horario livre para esta atividade na semana.'

    return render(request, 'editar_sessao.html', {
        'sessao': sessao, 'hora_inicio': form_hora, 'data_selecionada': form_data,
        'conflito': conflito, 'sugestao': sugestao, 'erro': erro,
    })


def continuar_visitante(request):
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    logout(request)
    return redirect("hoje")
