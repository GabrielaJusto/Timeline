import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


# MODELO DE TAREFAS
# Adaptação para Django da tabela tasks apresentada na documentação.
# UUID, data e timestamps usam os tipos próprios do Django.
# O horário continua como texto para preservar o padrão vazio "".

class Tarefa(models.Model):

    PRIORIDADES = [
        ("high", "Alta"),
        ("medium", "Média"),
        ("low", "Baixa"),
    ]

    # Identificador único gerado automaticamente no servidor.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Namespace e hash do token do navegador.
    # A view deve calcular e fornecer este valor no servidor.
    # Não é uma chave estrangeira para um usuário ou uma sessão.
    owner_id = models.TextField(editable=False)

    # Título obrigatório, com no máximo 120 caracteres.
    title = models.CharField(max_length=120)

    # Disciplina opcional: texto livre, sem tabela separada.
    subject = models.TextField(blank=True, default="")

    # Data de entrega obrigatória, recebida no formato YYYY-MM-DD.
    due_date = models.DateField()

    # Horário opcional: vazio ou HH:mm, por exemplo, 14:30.
    due_time = models.CharField(
        max_length=5,
        blank=True,
        default="",
        validators=[
            RegexValidator(
                regex=r"\A([01][0-9]|2[0-3]):[0-5][0-9]\Z",
                message="Informe um horário válido no formato HH:mm.",
            ),
        ],
    )

    # Prioridade obrigatória: high, medium ou low.
    priority = models.CharField(max_length=6, choices=PRIORIDADES)

    # False representa uma tarefa pendente; True representa concluída.
    completed = models.BooleanField(default=False)

    # Datas e horários registrados pelo Django ao salvar o objeto.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Preserva o nome físico da tabela e o índice da documentação.
        db_table = "tasks"
        indexes = [
            models.Index(
                fields=["owner_id", "due_date"],
                name="idx_tasks_owner_due",
            ),
        ]
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"

    def clean(self):
        super().clean()

        # Impede títulos e proprietários formados apenas por espaços.
        erros = {}
        if not isinstance(self.title, str) or not self.title.strip():
            erros["title"] = "Informe o título da tarefa."
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            erros["owner_id"] = "Informe o identificador do navegador."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return self.title


# Ao salvar pela view, use tarefa.full_clean() antes de tarefa.save().
# save() sozinho não executa as validações do modelo.
# Toda consulta deve ser filtrada pelo owner_id calculado no servidor.


class Disciplina(models.Model):
    periodo_id = models.IntegerField()
    nome = models.CharField(max_length=120)
    codigo = models.CharField(max_length=20, blank=True)
    professor = models.CharField(max_length=120, blank=True)
    cor_hex = models.CharField(max_length=7, blank=True)

    def __str__(self):
        return self.nome


class Atividade(models.Model):
    TIPOS = [
        ("prova", "Prova"),
        ("trabalho", "Trabalho"),
        ("lista", "Lista"),
        ("leitura", "Leitura"),
        ("projeto", "Projeto"),
        ("outro", "Outro"),
    ]

    STATUS = [
        ("planejada", "Planejada"),
        ("em_andamento", "Em andamento"),
        ("concluida", "Concluída"),
        ("nao_concluida", "Não concluída"),
        ("em_risco", "Em risco"),
        ("atrasada", "Atrasada"),
    ]

    usuario_id = models.IntegerField()
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    titulo = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    prazo = models.DateTimeField()
    dificuldade = models.IntegerField(null=True, blank=True)
    peso_nota = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True
    )
    importancia = models.IntegerField(null=True, blank=True)
    duracao_estimada_min = models.IntegerField(null=True, blank=True)
    duracao_real_min = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS, default="planejada"
    )
    fragmentavel = models.BooleanField(default=False)
    score_prioridade = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )

    def __str__(self):
        return self.titulo


class Compromisso(models.Model):
    usuario_id = models.IntegerField()
    titulo = models.CharField(max_length=120)
    categoria = models.CharField(max_length=50)
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    regra_recorrencia = models.TextField(blank=True)
    flexivel = models.BooleanField(default=False)

    def __str__(self):
        return self.titulo


class Planejamento(models.Model):
    usuario_id = models.IntegerField()
    semana_inicio = models.DateField()
    semana_fim = models.DateField()
    versao = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, default="ativo")
    gerado_em = models.DateTimeField(auto_now_add=True)
    horas_disponiveis = models.DecimalField(
        max_digits=7, decimal_places=2, default=0
    )
    horas_alocadas = models.DecimalField(
        max_digits=7, decimal_places=2, default=0
    )

    def __str__(self):
        return f"Planejamento {self.semana_inicio} - v{self.versao}"


class Aula(models.Model):
    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE)
    dia_semana = models.PositiveSmallIntegerField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    local = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.disciplina} - {self.hora_inicio}"


class Execucao(models.Model):
    atividade = models.ForeignKey(Atividade, on_delete=models.CASCADE)
    tempo_previsto_min = models.PositiveIntegerField()
    tempo_real_min = models.PositiveIntegerField(null=True, blank=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    desvio_percentual = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Execução da atividade {self.atividade_id}"


class AlertaCarga(models.Model):
    planejamento = models.ForeignKey(Planejamento, on_delete=models.CASCADE)
    indice_carga = models.DecimalField(max_digits=7, decimal_places=2)
    nivel = models.CharField(max_length=30)
    recomendacao = models.TextField(blank=True)
    gerado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alerta de carga {self.planejamento_id} - {self.nivel}"
