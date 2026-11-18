# Correções dos fluxos de tarefas e calendário

## 1. Corrigir seleção individual e filtros nas ações em lote
Permitir marcar qualquer subconjunto (por exemplo, quatro tarefas), exibir a quantidade selecionada e aplicar a ação apenas a esses itens. O controle de seleção da página indica seleção parcial. Buscar, filtrar tipo/status/recorrência e paginar continuam funcionando; mudar a data mantém horário, filtros e ordenação. Cada ação só altera tarefas da conta conectada.

## 2. Corrigir criação e edição de tarefas recorrentes
Salvar frequência e término da repetição. Criar ocorrências diárias, semanais e mensais até a data final, inclusive, preservando horário e duração. Meses curtos usam o último dia e retomam o dia original no mês seguinte. A edição permite escolher somente esta ocorrência ou esta e as próximas; as anteriores são preservadas. Reduzir/parar a série move as ocorrências excedentes para a lixeira, preservando suas subetapas. A edição de série não duplica ocorrências existentes. Séries antigas regulares têm sua regra recuperada na migração.

## 3. Exibir todos os intervalos livres de 06h a 23h
Descontar tarefas pendentes, aulas, compromissos e sessões, unificando sobreposições. Uma tarefa de 13h a 14h deixa livres 06h–13h e 14h–23h. A visualização mostra o dia inteiro, inclusive hoje; a reserva impede horários passados e recalcula conflitos ao salvar. Dias sem intervalos não mostram a seção.

## 4. Sincronizar conclusão de tarefas com suas subetapas
Concluir a tarefa quando sua última etapa pendente for concluída. Reabrir a tarefa como em andamento ao reabrir uma etapa ou adicionar uma nova etapa pendente. Atualização atômica por tarefa e isolada por conta.

## 5. Permitir informar início e término da tarefa
Melhoria complementar: adicionar horário de término na criação (incluindo modal) e edição. A diferença é salva como duração estimada e usada no cálculo de disponibilidade. O término deve ser posterior ao início no mesmo dia. Sem duração, tarefas agendadas ocupam uma hora.

## Como validar
Executar `python manage.py migrate` e `python manage.py test core`.
Para os testes de navegador: instalar `requirements-dev.txt`, executar `python -m playwright install chromium`, definir `RUN_BROWSER_TESTS=1` e executar `python manage.py test core.test_ui_fluxos`.

Os testes usam banco separado; os dados locais de demonstração não fazem parte do pull request.
