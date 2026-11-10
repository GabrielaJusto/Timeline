
from django.contrib import admin
from django.urls import path
from core import views
from core import views_ia
from core import views_organizacao as organizacao

urlpatterns = [
    path("tarefas/<int:atividade_id>/editar/", organizacao.editar_tarefa, name="editar_tarefa"),
    path("tarefas/<int:atividade_id>/excluir/", organizacao.excluir_tarefa, name="excluir_tarefa"),
    path("tarefas/<int:atividade_id>/subtarefas/", organizacao.subtarefa, name="subtarefa"),
    path("tarefas/lote/", organizacao.acoes_lote, name="acoes_lote"),
    path("lixeira/", organizacao.lixeira, name="lixeira"),
    path("lixeira/<str:tipo>/<int:registro_id>/restaurar/", organizacao.restaurar, name="restaurar"),
    path("agenda/sessao/nova/", organizacao.criar_sessao, name="criar_sessao"),
    path("agenda/exportar/", organizacao.exportar_agenda, name="exportar_agenda"),
    path("planejamento/ia/", views_ia.personalizacao_ia, name="personalizacao_ia"),
    path("planejamento/ia/<int:proposta_id>/aceitar/", views_ia.aceitar_ia, name="aceitar_ia"),
    path("planejamento/ia/<int:proposta_id>/rejeitar/", views_ia.rejeitar_ia, name="rejeitar_ia"),
    path("admin/", admin.site.urls),
    # Autentica??o
    path("login/", views.pagina_login, name="login"),
    path("logout/", views.pagina_logout, name="logout"),
    path("cadastro/", views.pagina_cadastro, name="cadastro"),

    # P?gina inicial
    path("", views.inicio, name="inicio"),

    # Hoje
    path("hoje/", views.hoje, name="hoje"),

    # Tarefas
    path("tarefas/", organizacao.tarefas, name="tarefas"),

    path(
        "tarefas/<int:atividade_id>/alternar-status/",
        views.alternar_status_tarefa,
        name="alternar_status_tarefa",
    ),

    path(
        "tarefas/<int:atividade_id>/nao-concluida/",
        views.marcar_atividade_nao_concluida,
        name="marcar_atividade_nao_concluida",
    ),

    path(
        "adicionar-tarefa/",
        organizacao.adicionar_tarefa,
        name="adicionar_tarefa",
    ),

    # Agenda
    path("agenda/", organizacao.agenda, name="agenda"),

    path(
        "agenda/semana/",
        organizacao.agenda_semanal,
        name="agenda_semana",
    ),

    path(
        "novo-compromisso/",
        organizacao.novo_compromisso,
        name="novo_compromisso",
    ),

    path(
        "excluir-compromisso/<int:compromisso_id>/",
        organizacao.excluir_compromisso,
        name="excluir_compromisso",
    ),

    path("agenda/mes/", organizacao.agenda_mensal, name="agenda_mes"),

    # Planejamento inteligente
    path(
        "planejamento/",
        views.planejamento,
        name="planejamento",
    ),

        # Edicao manual das sessoes do planejamento
    path(
        "planejamento/sessao/<int:sessao_id>/editar/",
        views.editar_sessao_planejamento,
        name="editar_sessao_planejamento",
    ),

    # Aceitar proposta de reagendamento
    path(
        "planejamento/proposta/<int:proposta_id>/aceitar/",
        views.aceitar_proposta_reagendamento,
        name="aceitar_proposta_reagendamento",
    ),

    # Rejeitar proposta de reagendamento
    path(
        "planejamento/proposta/<int:proposta_id>/rejeitar/",
        views.rejeitar_proposta_reagendamento,
        name="rejeitar_proposta_reagendamento",
    ),

    # Historico de planejamentos
    path(
        "planejamento/historico/",
        views.historico_planejamentos,
        name="historico_planejamentos",
    ),

    # Progresso
    path("progresso/", views.progresso, name="progresso"),

    # Configurações
    path(
        "configuracoes/",
        views.configuracoes,
        name="configuracoes",
    ),

    # Notificações
    path(
        "notificacoes/",
        views.notificacoes,
        name="notificacoes",
    ),
]
