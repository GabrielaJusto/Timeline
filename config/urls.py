
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("hoje/", views.hoje, name="hoje"),
    path("tarefas/", views.tarefas, name="tarefas"),
    path(
    "tarefas/<int:atividade_id>/alternar-status/",
    views.alternar_status_tarefa,
    name="alternar_status_tarefa"
    ),
    path("adicionar-tarefa/", views.adicionar_tarefa, name="adicionar_tarefa"),
    path("", views.inicio, name="inicio"),
    path("agenda/", views.agenda, name="agenda"),
    path("planejamento/", views.planejamento, name="planejamento"),
    path("agenda/semana/", views.agenda_semanal, name="agenda_semana"),
    path("agenda/mes/", views.agenda_mensal, name="agenda_mes"),  
    path("novo-compromisso/", views.novo_compromisso, name="novo_compromisso"),
    path("excluir-compromisso/<int:compromisso_id>/", views.excluir_compromisso, name="excluir_compromisso"),
    path("progresso/", views.progresso, name="progresso"),
    path("configuracoes/", views.configuracoes, name="configuracoes"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
]
