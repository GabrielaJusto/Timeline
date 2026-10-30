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