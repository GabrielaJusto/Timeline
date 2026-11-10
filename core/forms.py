from django import forms
from .models import Atividade

class AtividadeForm(forms.ModelForm):
    nome_disciplina = forms.CharField(
        label="Disciplina",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Ex.: Cálculo 1"
        })
    )

    data_entrega = forms.DateField(
        label="Data de entrega",
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d"
        )
    )

    horario = forms.TimeField(
        label="Horário",
        required=False,
        widget=forms.TimeInput(
            attrs={"type": "time"},
            format="%H:%M"
        )
    )

    class Meta:
        model = Atividade
        fields = ["titulo", "tipo"]

        widgets = {
            "titulo": forms.TextInput(attrs={
                "placeholder": "Ex.: Lista de exercícios de Cálculo"
            }),
        }

from .models import Compromisso

class CompromissoForm(forms.ModelForm):
    class Meta:
        model = Compromisso
        fields = ["titulo", "categoria", "inicio", "fim", "flexivel"]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

class RecorrenciaFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["frequencia"] = forms.ChoiceField(label="Repetir", required=False,
            choices=[("", "Não repetir"), ("diaria", "Diariamente"), ("semanal", "Semanalmente"), ("mensal", "Mensalmente")])
        self.fields["repetir_ate"] = forms.DateField(label="Repetir até", required=False,
            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    def clean(self):
        from datetime import timedelta
        from django.utils import timezone
        dados = super().clean()
        inicio = dados.get("data_entrega")
        if inicio is None and dados.get("inicio"):
            inicio = timezone.localtime(dados["inicio"]).date()
        fim = dados.get("repetir_ate")
        if dados.get("frequencia"):
            if not fim:
                self.add_error("repetir_ate", "Informe a data de término da repetição.")
            elif inicio and (fim < inicio or fim > inicio + timedelta(days=366)):
                self.add_error("repetir_ate", "Escolha uma data entre o primeiro evento e os próximos 366 dias.")
        return dados


class AtividadeRecorrenteForm(RecorrenciaFormMixin, AtividadeForm):
    pass


class CompromissoRecorrenteForm(RecorrenciaFormMixin, CompromissoForm):
    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["fim"] <= dados["inicio"]:
            self.add_error("fim", "O término deve ser depois do início.")
        return dados


class SessaoLivreForm(forms.Form):
    atividade = forms.ModelChoiceField(queryset=Atividade.objects.none(), label="Tarefa")
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hora_inicio = forms.TimeField(label="Início", widget=forms.TimeInput(attrs={"type": "time"}))
    duracao_min = forms.IntegerField(label="Duração em minutos", min_value=15, max_value=480, initial=60)

    def __init__(self, *args, usuario_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["atividade"].queryset = Atividade.objects.filter(usuario_id=usuario_id).exclude(status="concluida").order_by("prazo")
