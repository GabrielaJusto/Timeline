from django.contrib import admin

from .models import PerfilAluno


@admin.register(PerfilAluno)
class PerfilAlunoAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "faculdade", "usuario")
    search_fields = ("nome_completo", "faculdade", "usuario__username", "usuario__email")
