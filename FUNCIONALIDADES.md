# Organização de tarefas e agenda

As oito melhorias estão acessíveis pela lista de tarefas e pelo calendário. É necessário entrar ou criar uma conta. Os registros antigos associados ao usuário de teste 1 permanecem com esse identificador; não são redistribuídos entre contas.

1. **Editar e excluir:** botões em cada tarefa; exclusão com confirmação e envio à lixeira. Alterações em séries afetam apenas a ocorrência selecionada.
2. **Recorrência:** formulários de nova tarefa e novo compromisso oferecem frequência diária, semanal e mensal. A data final é obrigatória e limitada a 366 dias após a primeira ocorrência. As ocorrências são criadas de uma vez em transação. No caso mensal, o dia 31 vira o último dia nos meses mais curtos e volta ao dia 31 quando possível.
3. **Horários livres:** agenda diária e semanal mostram intervalos de ao menos 15 minutos entre 07h e 23h. Consideram aulas, compromissos (inclusive atravessando dias) e sessões de planos ativos. Prazos de tarefas são entregas e não bloqueiam tempo. Sessões antigas sem horário usam o mesmo horário virtual do editor de planejamento, iniciando às 09h.
4. **Desempenho:** tarefas paginadas em 20 registros, disciplinas carregadas junto das tarefas e subtarefas em uma consulta adicional. Calendário diário, semanal e mensal compartilham quatro consultas para buscar tarefas, compromissos, sessões e aulas. Índices por usuário, exclusão e data.
5. **Subtarefas:** seção de etapas em cada tarefa, com cadastro e conclusão individual. Concluir etapas não conclui automaticamente a atividade principal.
6. **Lote:** selecionar registros da página e concluir, mudar data mantendo horário ou enviar à lixeira. Filtros permanecem nos links de paginação.
7. **Lixeira:** acessível pelo menu de tarefas e pelas agendas. Restaura tarefas, etapas e sessões, ou compromissos, individualmente. A exclusão não apaga o banco; não existe limpeza definitiva automática. Restaurar uma sessão preserva seu horário original; confira possíveis conflitos se a agenda tiver sido modificada.
8. **Exportação:** barra das agendas permite escolher até 366 dias e baixar um arquivo `.ics` com tarefas, compromissos, aulas e sessões. Exportação pontual, sem sincronização automática. Horários em UTC, textos escapados e linhas dobradas em até 75 bytes.

## Banco e validação

Aplicar `python manage.py migrate` antes de iniciar o servidor. A migração `0008_organizacao_tarefas_agenda` adiciona os campos sem excluir os registros existentes.

Executar `python manage.py test core` e `python manage.py check`. Os testes usam banco temporário e cobrem edição, validação, recorrência, autorização, restauração, subtarefas, ações em lote, consultas, paginação, intervalos, reservas e exportação.

O projeto mantém o fuso horário já configurado em `config/settings.py`. Os formulários e os calendários usam esse mesmo fuso.
