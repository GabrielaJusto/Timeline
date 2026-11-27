from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import PerfilAluno


class CadastroForm(UserCreationForm):
    nome_completo = forms.CharField(
        label="Nome completo", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    faculdade = forms.CharField(
        label="Faculdade", max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "organization"}),
    )
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "autocomplete": "bday"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        help_text="Usaremos este endereço para recuperar sua senha.",
    )

    class Meta(UserCreationForm.Meta):
        fields = (
            "nome_completo", "faculdade", "data_nascimento", "email",
            "username", "password1", "password2",
        )

    def clean_nome_completo(self):
        return " ".join(self.cleaned_data["nome_completo"].split())

    def clean_data_nascimento(self):
        data = self.cleaned_data["data_nascimento"]
        if data > timezone.localdate():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
        return data

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado. Entre ou recupere sua senha.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        partes = self.cleaned_data["nome_completo"].split(" ", 1)
        usuario.first_name = partes[0]
        usuario.last_name = partes[1] if len(partes) > 1 else ""
        if commit:
            with transaction.atomic():
                usuario.save()
                PerfilAluno.objects.update_or_create(
                    usuario=usuario,
                    defaults={
                        "nome_completo": self.cleaned_data["nome_completo"],
                        "faculdade": self.cleaned_data["faculdade"],
                        "data_nascimento": self.cleaned_data["data_nascimento"],
                    },
                )
        return usuario


class PerfilForm(forms.Form):
    """
    Edição dos dados da conta pela tela de Configurações.

    Usa as mesmas regras do cadastro: nome sem espaços repetidos,
    nascimento que não está no futuro e e-mail que não pertence a outra conta.
    """

    nome_completo = forms.CharField(
        label="Nome completo", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    faculdade = forms.CharField(
        label="Faculdade", max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "organization"}),
    )
    data_nascimento = forms.DateField(
        label="Data de nascimento", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "autocomplete": "bday"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        help_text="Usado para recuperar a senha.",
    )

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        perfil = getattr(usuario, "perfil_aluno", None)
        kwargs.setdefault("initial", {
            "nome_completo": (perfil.nome_completo if perfil else "") or usuario.get_full_name(),
            "faculdade": perfil.faculdade if perfil else "",
            "data_nascimento": perfil.data_nascimento if perfil else None,
            "email": usuario.email,
        })
        super().__init__(*args, **kwargs)

    def clean_nome_completo(self):
        nome = " ".join(self.cleaned_data["nome_completo"].split())
        if not nome:
            raise forms.ValidationError("Informe seu nome.")
        return nome

    def clean_faculdade(self):
        faculdade = " ".join(self.cleaned_data["faculdade"].split())
        if not faculdade:
            raise forms.ValidationError("Informe sua faculdade.")
        return faculdade

    def clean_data_nascimento(self):
        data = self.cleaned_data["data_nascimento"]
        if data and data > timezone.localdate():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
        return data

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        outras_contas = get_user_model().objects.filter(email__iexact=email).exclude(pk=self.usuario.pk)
        if outras_contas.exists():
            raise forms.ValidationError("Este e-mail já pertence a outra conta.")
        return email

    def save(self):
        dados = self.cleaned_data
        partes = dados["nome_completo"].split(" ", 1)
        self.usuario.first_name = partes[0]
        self.usuario.last_name = partes[1] if len(partes) > 1 else ""
        self.usuario.email = dados["email"]
        with transaction.atomic():
            self.usuario.save(update_fields=["first_name", "last_name", "email"])
            PerfilAluno.objects.update_or_create(
                usuario=self.usuario,
                defaults={
                    "nome_completo": dados["nome_completo"],
                    "faculdade": dados["faculdade"],
                    "data_nascimento": dados["data_nascimento"],
                },
            )
        return self.usuario
