from django.shortcuts import render
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render
from .models import Atividade
from django.shortcuts import redirect, get_object_or_404
from .forms import AtividadeForm
from datetime import datetime, time
from .forms import CompromissoForm
from .models import Atividade, Compromisso


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
    progresso = int((concluidas / total_atividades * 100)) if total_atividades > 0 else 0
    data_atual = timezone.localdate()
    inicio_semana = data_atual - timedelta(days=data_atual.weekday())
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]
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

def inicio(request):
    return render(request, "index.html")


def agenda(request):
  from .models import Aula
  aulas = Aula.objects.select_related("disciplina").all().order_by("dia_semana","hora_inicio")
  return render(request, "agenda.html", {"aulas": aulas})


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