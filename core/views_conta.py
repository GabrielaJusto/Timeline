import json

from django import forms
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Atividade, Compromisso, Planejamento, SessaoPlanejada


# ==========================================
# BAIXAR MEUS DADOS
# ==========================================

def dados_da_conta(usuario):
    """
    Tudo o que o Timeline guarda sobre a conta, em formato legível.

    Inclui o que está na lixeira, porque esses registros
    continuam no banco até a conta ser excluída.
    """

    perfil = getattr(usuario, "perfil_aluno", None)

    tarefas = (
        Atividade.todos.filter(usuario_id=usuario.id)
        .prefetch_related("subtarefas")
        .order_by("prazo", "id")
    )
    compromissos = Compromisso.todos.filter(usuario_id=usuario.id).order_by("inicio", "id")
    planejamentos = Planejamento.objects.filter(usuario_id=usuario.id).order_by("semana_inicio", "versao")
    sessoes = (
        SessaoPlanejada.todas.filter(planejamento__usuario_id=usuario.id)
        .select_related("atividade")
        .order_by("data", "id")
    )

    return {
        "gerado_em": timezone.localtime(),
        "conta": {
            "usuario": usuario.get_username(),
            "email": usuario.email,
            "nome": usuario.get_full_name(),
            "criada_em": usuario.date_joined,
            "ultimo_acesso": usuario.last_login,
        },
        "perfil": {
            "nome_completo": perfil.nome_completo,
            "faculdade": perfil.faculdade,
            "data_nascimento": perfil.data_nascimento,
        } if perfil else None,
        "tarefas": [
            {
                "titulo": t.titulo,
                "disciplina": t.nome_disciplina,
                "tipo": t.get_tipo_display(),
                "prazo": t.prazo,
                "status": t.get_status_display(),
                "na_lixeira": t.excluido_em is not None,
                "etapas": [
                    {"titulo": e.titulo, "concluida": e.concluida}
                    for e in t.subtarefas.all()
                ],
            }
            for t in tarefas
        ],
        "compromissos": [
            {
                "titulo": c.titulo,
                "categoria": c.categoria,
                "inicio": c.inicio,
                "fim": c.fim,
                "flexivel": c.flexivel,
                "na_lixeira": c.excluido_em is not None,
            }
            for c in compromissos
        ],
        "planejamentos": [
            {
                "semana_inicio": p.semana_inicio,
                "semana_fim": p.semana_fim,
                "versao": p.versao,
                "status": p.status,
                "horas_disponiveis": p.horas_disponiveis,
                "horas_alocadas": p.horas_alocadas,
                "sessoes": [
                    {
                        "data": s.data,
                        "hora_inicio": s.hora_inicio,
                        "duracao_min": s.duracao_min,
                        "tarefa": s.atividade.titulo,
                    }
                    for s in sessoes if s.planejamento_id == p.id
                ],
            }
            for p in planejamentos
        ],
    }


@login_required
@require_GET
def baixar_meus_dados(request):
    conteudo = json.dumps(
        dados_da_conta(request.user),
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        indent=2,
    )
    resposta = HttpResponse(conteudo, content_type="application/json; charset=utf-8")
    nome = f"timeline-meus-dados-{timezone.localdate():%Y-%m-%d}.json"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "private, no-store"
    return resposta


# ==========================================
# EXCLUIR CONTA
# ==========================================

class ExcluirContaForm(forms.Form):
    """
    Confirmação da exclusão.

    Conta com senha: pede a senha atual.
    Conta criada pelo Google, sem senha: pede o nome de usuário digitado.
    """

    confirmacao = forms.CharField(strip=False)
    ciente = forms.BooleanField(
        label="Entendo que tarefas, compromissos e planejamentos serão apagados e que isso não pode ser desfeito.",
    )

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.pede_senha = usuario.has_usable_password()
        campo = self.fields["confirmacao"]
        if self.pede_senha:
            campo.label = "Senha atual"
            campo.widget = forms.PasswordInput(attrs={"autocomplete": "current-password"})
        else:
            campo.label = f"Digite seu usuário ({usuario.get_username()}) para confirmar"
            campo.widget = forms.TextInput(attrs={"autocomplete": "off"})

    def clean_confirmacao(self):
        valor = self.cleaned_data["confirmacao"]
        if self.pede_senha:
            if not self.usuario.check_password(valor):
                raise forms.ValidationError("Senha incorreta.")
        elif valor.strip() != self.usuario.get_username():
            raise forms.ValidationError("O usuário digitado não confere.")
        return valor


def apagar_dados_da_conta(usuario):
    """
    Apaga a conta e tudo o que pertence a ela.

    Tarefas, compromissos e planejamentos guardam o dono em usuario_id,
    um número, e não numa chave estrangeira: o banco não os apaga
    sozinho junto com o usuário, por isso a exclusão é feita aqui.
    Etapas, sessões, execuções, alertas e propostas saem em cascata.
    """

    with transaction.atomic():
        Planejamento.objects.filter(usuario_id=usuario.id).delete()
        Atividade.todos.filter(usuario_id=usuario.id).delete()
        Compromisso.todos.filter(usuario_id=usuario.id).delete()
        # Perfil, login do Google e e-mails cadastrados saem em cascata.
        usuario.delete()


@login_required
def excluir_conta(request):
    usuario = request.user
    form = ExcluirContaForm(request.POST or None, usuario=usuario)

    if request.method == "POST" and form.is_valid():
        logout(request)
        apagar_dados_da_conta(usuario)
        return render(request, "conta-excluida.html")

    return render(request, "excluir-conta.html", {
        "form": form,
        "total_tarefas": Atividade.todos.filter(usuario_id=usuario.id).count(),
        "total_compromissos": Compromisso.todos.filter(usuario_id=usuario.id).count(),
        "total_planejamentos": Planejamento.objects.filter(usuario_id=usuario.id).count(),
    })
