import calendar
from datetime import date, datetime, time, timedelta, timezone as utc_timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Atividade, Compromisso, Planejamento, SessaoPlanejada, Subtarefa
from .forms import AtividadeForm, AtividadeRecorrenteForm, CompromissoRecorrenteForm, SessaoLivreForm
from .agenda_services import salvar_recorrencias, dados_periodo, horarios_livres, limites, escapar_ics, dobrar_ics


def ler_data(valor, padrao):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        return padrao


@login_required
def tarefas(request, formulario=None):
    atividades = Atividade.objects.filter(usuario_id=request.user.id).select_related("disciplina")
    busca = request.GET.get("busca", "").strip()
    status, tipo = request.GET.get("status", ""), request.GET.get("tipo", "")
    ordem = request.GET.get("ordem", "prazo")
    if busca:
        atividades = atividades.filter(Q(titulo__icontains=busca) | Q(nome_disciplina__icontains=busca) | Q(disciplina__nome__icontains=busca))
    if status in dict(Atividade.STATUS):
        atividades = atividades.filter(status=status)
    if tipo in dict(Atividade.TIPOS):
        atividades = atividades.filter(tipo=tipo)
    totais = atividades.aggregate(total=Count("id"), concluidas=Count("id", filter=Q(status="concluida")))
    ordenacao = {"prazo_desc": "-prazo", "titulo": "titulo"}.get(ordem, "prazo")
    pagina = Paginator(atividades.order_by(ordenacao, "id").prefetch_related("subtarefas"), 20).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return render(request, "tarefas.html", {"atividades": pagina, "pagina": pagina, "total": totais["total"],
        "concluidas": totais["concluidas"], "pendentes": totais["total"] - totais["concluidas"],
        "busca": busca, "status_selecionado": status, "tipo_selecionado": tipo, "ordem_selecionada": ordem,
        "opcoes_status": Atividade.STATUS, "opcoes_tipo": Atividade.TIPOS, "parametros": parametros.urlencode(),
        "form": formulario if formulario is not None else AtividadeRecorrenteForm()})


@login_required
def adicionar_tarefa(request):
    form = AtividadeRecorrenteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        atividade = form.save(commit=False)
        atividade.usuario_id = request.user.id
        atividade.nome_disciplina = form.cleaned_data["nome_disciplina"].strip()
        atividade.prazo = timezone.make_aware(datetime.combine(form.cleaned_data["data_entrega"], form.cleaned_data["horario"] or time(23, 59)))
        salvar_recorrencias(atividade, form.cleaned_data["frequencia"], form.cleaned_data["repetir_ate"])
        messages.success(request, "Tarefa salva. As repetições, quando solicitadas, já aparecem na agenda.")
        return redirect("tarefas")
    if request.method == "POST" and request.POST.get("origem") == "tarefas":
        return tarefas(request, formulario=form)
    return render(request, "organizacao/formulario.html", {"form": form, "titulo": "Adicionar tarefa"})


@login_required
def editar_tarefa(request, atividade_id):
    atividade = get_object_or_404(Atividade, pk=atividade_id, usuario_id=request.user.id)
    prazo = timezone.localtime(atividade.prazo)
    form = AtividadeForm(request.POST or None, instance=atividade, initial={"data_entrega": prazo.date(), "horario": prazo.time()})
    if request.method == "POST" and form.is_valid():
        atividade = form.save(commit=False)
        atividade.nome_disciplina = form.cleaned_data["nome_disciplina"].strip()
        atividade.prazo = timezone.make_aware(datetime.combine(form.cleaned_data["data_entrega"], form.cleaned_data["horario"] or time(23, 59)))
        atividade.save()
        messages.success(request, "Tarefa atualizada. Em séries recorrentes, apenas esta ocorrência foi alterada.")
        return redirect("tarefas")
    return render(request, "organizacao/formulario.html", {"form": form, "titulo": "Editar tarefa"})


@login_required
@require_POST
def excluir_tarefa(request, atividade_id):
    atividade = get_object_or_404(Atividade, pk=atividade_id, usuario_id=request.user.id)
    atividade.excluido_em = timezone.now()
    atividade.save(update_fields=["excluido_em"])
    messages.success(request, "Tarefa movida para a lixeira. Você pode restaurá-la.")
    return redirect("tarefas")


@login_required
@require_POST
def acoes_lote(request):
    ids = request.POST.getlist("atividades")
    if not ids or any(not i.isdecimal() or len(i) > 18 for i in ids):
        messages.error(request, "Selecione ao menos uma tarefa válida.")
        return redirect("tarefas")
    tarefas = Atividade.objects.filter(usuario_id=request.user.id, pk__in=ids)
    acao = request.POST.get("acao")
    if acao == "concluir":
        quantidade = tarefas.update(status="concluida")
    elif acao == "excluir":
        quantidade = tarefas.update(excluido_em=timezone.now())
    elif acao == "adiar":
        nova_data = ler_data(request.POST.get("nova_data"), None)
        if nova_data is None:
            messages.error(request, "Informe uma data válida. Nenhuma tarefa foi alterada.")
            return redirect("tarefas")
        with transaction.atomic():
            registros = list(tarefas.select_for_update())
            for tarefa in registros:
                tarefa.prazo = timezone.make_aware(datetime.combine(nova_data, timezone.localtime(tarefa.prazo).time()))
            Atividade.objects.bulk_update(registros, ["prazo"])
        quantidade = len(registros)
    else:
        return HttpResponseBadRequest("Ação inválida")
    messages.success(request, f"{quantidade} tarefa(s) atualizada(s).")
    return redirect("tarefas")


@login_required
@require_POST
def subtarefa(request, atividade_id):
    atividade = get_object_or_404(Atividade, pk=atividade_id, usuario_id=request.user.id)
    if request.POST.get("subtarefa_id"):
        item = get_object_or_404(Subtarefa, pk=request.POST["subtarefa_id"], atividade=atividade)
        item.concluida = not item.concluida
        item.save(update_fields=["concluida"])
    else:
        titulo = request.POST.get("titulo", "").strip()
        if not titulo or len(titulo) > 120:
            messages.error(request, "Informe uma etapa de até 120 caracteres.")
            return redirect("tarefas")
        Subtarefa.objects.create(atividade=atividade, titulo=titulo)
    return redirect("tarefas")


@login_required
def lixeira(request):
    tarefas = Atividade.todos.filter(usuario_id=request.user.id, excluido_em__isnull=False).order_by("-excluido_em")
    compromissos = Compromisso.todos.filter(usuario_id=request.user.id, excluido_em__isnull=False).order_by("-excluido_em")
    return render(request, "organizacao/lixeira.html", {
        "tarefas": Paginator(tarefas, 20).get_page(request.GET.get("tarefas_page")),
        "compromissos": Paginator(compromissos, 20).get_page(request.GET.get("compromissos_page"))})


@login_required
@require_POST
def restaurar(request, tipo, registro_id):
    modelo = {"tarefa": Atividade, "compromisso": Compromisso}.get(tipo)
    if modelo is None:
        return HttpResponseBadRequest("Tipo inválido")
    registro = get_object_or_404(modelo.todos, pk=registro_id, usuario_id=request.user.id, excluido_em__isnull=False)
    registro.excluido_em = None
    registro.save(update_fields=["excluido_em"])
    messages.success(request, "Registro restaurado, incluindo suas etapas e sessões vinculadas.")
    return redirect("lixeira")


@login_required
def novo_compromisso(request):
    form = CompromissoRecorrenteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        compromisso = form.save(commit=False)
        compromisso.usuario_id = request.user.id
        salvar_recorrencias(compromisso, form.cleaned_data["frequencia"], form.cleaned_data["repetir_ate"])
        return redirect("agenda_semana")
    return render(request, "organizacao/formulario.html", {"form": form, "titulo": "Novo compromisso"})


@login_required
@require_POST
def excluir_compromisso(request, compromisso_id):
    compromisso = get_object_or_404(Compromisso, pk=compromisso_id, usuario_id=request.user.id)
    compromisso.excluido_em = timezone.now()
    compromisso.save(update_fields=["excluido_em"])
    messages.success(request, "Compromisso movido para a lixeira.")
    return redirect("agenda_semana")


@login_required
def agenda_semanal(request):
    hoje = timezone.localdate()
    referencia = ler_data(request.GET.get("semana"), hoje)
    inicio = referencia - timedelta(days=referencia.weekday())
    fim = inicio + timedelta(days=6)
    dias = dados_periodo(request.user.id, inicio, fim)
    for dia in dias:
        dia["livres"] = horarios_livres(dia)
    total = sum(len(d["tarefas"]) for d in dias)
    concluidas = sum(t.status == "concluida" for d in dias for t in d["tarefas"])
    organizados = sum(bool(d["tarefas"] or d["compromissos"] or d["aulas"] or d["sessoes"]) for d in dias)
    return render(request, "agenda-semana.html", {"dias": dias, "data_atual": hoje, "inicio_semana": inicio,
        "fim_semana": fim, "semana_anterior": inicio - timedelta(days=7), "semana_seguinte": inicio + timedelta(days=7),
        "titulo_semana": f"{inicio:%d/%m} a {fim:%d/%m/%Y}", "tarefas_total": total, "tarefas_concluidas": concluidas,
        "tarefas_percentual": round(concluidas * 100 / total) if total else 0,
        "dias_organizados": organizados, "dias_percentual": round(organizados * 100 / 7)})


@login_required
def agenda_mensal(request):
    hoje = timezone.localdate()
    inicio = ler_data(request.GET.get("mes"), hoje).replace(day=1)
    semanas = calendar.Calendar().monthdatescalendar(inicio.year, inicio.month)
    dias = dados_periodo(request.user.id, semanas[0][0], semanas[-1][-1])
    for dia in dias:
        dia.update(mes_atual=dia["data"].month == inicio.month, hoje=dia["data"] == hoje)
    nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return render(request, "agenda-mes.html", {"semanas": [dias[i:i+7] for i in range(0,len(dias),7)],
        "titulo_mes": f"{nomes[inicio.month-1]} {inicio.year}", "mes_anterior": inicio - timedelta(days=1),
        "proximo_mes": (inicio + timedelta(days=32)).replace(day=1)})


@login_required
def agenda(request):
    hoje = timezone.localdate()
    dia = dados_periodo(request.user.id, hoje, hoje)[0]
    eventos = []
    for c in dia["compromissos"]:
        eventos.append({"horario": timezone.localtime(c.inicio).time(), "titulo": c.titulo, "tipo": "Compromisso", "detalhe": c.categoria})
    for a in dia["aulas"]:
        eventos.append({"horario": a.hora_inicio, "titulo": a.disciplina.nome, "tipo": "Aula", "detalhe": a.local})
    for t in dia["tarefas"]:
        eventos.append({"horario": timezone.localtime(t.prazo).time(), "titulo": t.titulo, "tipo": "Tarefa", "detalhe": t.get_status_display()})
    for s in dia["sessoes"]:
        minuto = min(s.inicio_minuto, 1439)
        eventos.append({"horario": time(minuto // 60, minuto % 60), "titulo": s.atividade.titulo, "tipo": "Estudo", "detalhe": f"{s.duracao_min} min"})
    tarefas = Atividade.objects.filter(usuario_id=request.user.id)
    totais = tarefas.aggregate(total=Count("id"), concluidas=Count("id", filter=Q(status="concluida")))
    return render(request, "agenda.html", {"aulas": dia["aulas"], "eventos_do_dia": sorted(eventos,key=lambda e:e["horario"]),
        "tarefas_pendentes": tarefas.exclude(status="concluida").order_by("prazo")[:5],
        "total_tarefas": totais["total"], "tarefas_concluidas": totais["concluidas"],
        "percentual_tarefas": round(totais["concluidas"]*100/totais["total"]) if totais["total"] else 0,
        "dia_livre": {**dia, "livres": horarios_livres(dia)}})


@login_required
def criar_sessao(request):
    form = SessaoLivreForm(request.POST or None, usuario_id=request.user.id, initial={
        "data": request.GET.get("data"), "hora_inicio": request.GET.get("hora"), "duracao_min": request.GET.get("duracao",60)})
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        data, hora, duracao = dados["data"], dados["hora_inicio"], dados["duracao_min"]
        inicio = hora.hour * 60 + hora.minute
        with transaction.atomic():
            # Serializa as reservas desse usuário antes de recalcular a disponibilidade.
            from django.contrib.auth import get_user_model
            get_user_model().objects.select_for_update().get(pk=request.user.id)
            dia = dados_periodo(request.user.id, data, data)[0]
            disponivel = any(l["inicio"] <= inicio and inicio + duracao <= l["fim"] for l in horarios_livres(dia))
            prazo = timezone.make_aware(datetime.combine(data, hora)) + timedelta(minutes=duracao)
            if not disponivel:
                form.add_error(None, "O horário está ocupado ou fora da janela de estudo (07h–23h). Escolha outro intervalo.")
            elif prazo > dados["atividade"].prazo:
                form.add_error("data", "A sessão deve terminar antes do prazo da tarefa.")
            else:
                segunda = data - timedelta(days=data.weekday())
                plano = Planejamento.objects.filter(usuario_id=request.user.id, semana_inicio=segunda, status="ativo").order_by("-id").first()
                if plano is None:
                    plano = Planejamento.objects.create(usuario_id=request.user.id, semana_inicio=segunda, semana_fim=segunda+timedelta(days=6), disponibilidade_diaria={})
                SessaoPlanejada.objects.create(planejamento=plano, atividade=dados["atividade"], data=data, hora_inicio=hora, duracao_min=duracao)
                from decimal import Decimal
                plano.horas_alocadas += Decimal(duracao) / Decimal(60)
                disponibilidade = dict(plano.disponibilidade_diaria)
                minutos_dia = plano.sessoes.filter(data=data).aggregate(total=Sum("duracao_min"))["total"] or 0
                disponibilidade[data.isoformat()] = max(float(disponibilidade.get(data.isoformat(), 0)), minutos_dia / 60)
                plano.disponibilidade_diaria = disponibilidade
                plano.horas_disponiveis = max(plano.horas_disponiveis, Decimal(str(sum(disponibilidade.values()))))
                plano.save(update_fields=["horas_alocadas", "horas_disponiveis", "disponibilidade_diaria"])
                messages.success(request, "Sessão de estudo adicionada ao planejamento.")
                return redirect(f"/agenda/semana/?semana={segunda.isoformat()}")
    return render(request,"organizacao/formulario.html",{"form":form,"titulo":"Reservar horário de estudo"})


@login_required
def exportar_agenda(request):
    hoje = timezone.localdate()
    inicio = ler_data(request.GET.get("inicio"), hoje)
    fim = ler_data(request.GET.get("fim"), inicio + timedelta(days=90))
    if fim < inicio or (fim-inicio).days > 366:
        return HttpResponseBadRequest("Escolha um intervalo de até 366 dias, com término após o início.")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Timeline//Agenda//PT-BR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    stamp = timezone.now().astimezone(utc_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    def evento(uid, titulo, comeco, termino=None):
        linhas.extend(["BEGIN:VEVENT", f"UID:{uid}@timeline.local", f"DTSTAMP:{stamp}",
            "DTSTART:" + comeco.astimezone(utc_timezone.utc).strftime("%Y%m%dT%H%M%SZ")])
        if termino:
            linhas.append("DTEND:" + termino.astimezone(utc_timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        linhas.extend(["SUMMARY:" + escapar_ics(titulo), "END:VEVENT"])
    exportados = set()
    for dia in dados_periodo(request.user.id, inicio, fim):
        for c in dia["compromissos"]:
            if c.id not in exportados:
                evento(f"compromisso-{c.id}", c.titulo, c.inicio, c.fim)
                exportados.add(c.id)
        for t in dia["tarefas"]:
            evento(f"tarefa-{t.id}", t.titulo, t.prazo)
        for a in dia["aulas"]:
            comeco = timezone.make_aware(datetime.combine(dia["data"], a.hora_inicio))
            termino = timezone.make_aware(datetime.combine(dia["data"], a.hora_fim))
            evento(f"aula-{a.id}-{dia['data']}", a.disciplina.nome, comeco, termino)
        for s in dia["sessoes"]:
            comeco = limites(s.data)[0] + timedelta(minutes=s.inicio_minuto)
            evento(f"sessao-{s.id}", "Estudo: " + s.atividade.titulo, comeco, comeco+timedelta(minutes=s.duracao_min))
    linhas.append("END:VCALENDAR")
    resposta = HttpResponse("\r\n".join(dobrar_ics(l) for l in linhas)+"\r\n",content_type="text/calendar; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="timeline.ics"'
    return resposta
