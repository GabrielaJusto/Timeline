from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import CompromissoForm
from .models import Compromisso


class CompromissoEdicaoForm(CompromissoForm):
    """
    Formulário de edição: os mesmos campos do cadastro,
    com rótulos acentuados e a regra de término depois do início.
    """

    class Meta(CompromissoForm.Meta):
        labels = {
            "titulo": "Título",
            "categoria": "Categoria",
            "inicio": "Início",
            "fim": "Término",
            "flexivel": "Horário flexível",
        }

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim and fim <= inicio:
            self.add_error("fim", "O término deve ser depois do início.")
        return dados


@login_required
def editar_compromisso(request, compromisso_id):
    """
    Altera título, categoria, horário e flexibilidade de um compromisso.

    Em séries recorrentes, só a ocorrência escolhida muda,
    o mesmo comportamento da edição de tarefas.
    """

    compromisso = get_object_or_404(Compromisso, pk=compromisso_id, usuario_id=request.user.id)
    form = CompromissoEdicaoForm(request.POST or None, instance=compromisso)

    if request.method == "POST" and form.is_valid():
        compromisso = form.save()
        messages.success(request, "Compromisso atualizado. Em séries recorrentes, apenas esta ocorrência foi alterada.")
        semana = timezone.localtime(compromisso.inicio).date().isoformat()
        return redirect(f"{reverse('agenda_semana')}?semana={semana}")

    return render(request, "editar-compromisso.html", {"form": form, "compromisso": compromisso})
