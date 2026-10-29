from django import forms
from .models import Atividade


class AtividadeForm(forms.ModelForm):
    data_entrega = forms.DateField(
        label="Data de entrega",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    horario = forms.TimeField(
        label="Horário",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )

    class Meta:
        model = Atividade
        fields = ["titulo", "disciplina", "tipo"]

        widgets = {
            "titulo": forms.TextInput(attrs={
                "placeholder": "Ex.: Lista de exercícios de Cálculo"
            }),
        }