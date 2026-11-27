# Timeline

Aplicativo Django para organizar tarefas, calendário e planejamento de estudos.

## Executar a versão atual

Requer Python 3.10 ou superior. Em um terminal na pasta do projeto:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8001 --noreload
```

Abra http://127.0.0.1:8001/. Encerre qualquer servidor anterior nessa porta antes de iniciar outro. O banco local e arquivos de configuração reais não fazem parte desta atualização; as migrações preparam o banco de cada participante.

## Alterações de interface e autenticação

- Marca e barra lateral com estilos compartilhados: símbolo, nome Timeline, navegação, cartão e botões de conta.
- Formulário de nova tarefa sobre a página atual, fechamento sem sair da página e redirecionamento para Tarefas após salvar.
- Cadastro com nome completo, faculdade, nascimento e e-mail; erros destacados no formulário.
- Entrada com Google e recuperação de senha por e-mail com link temporário.

O cadastro por usuário e senha funciona sem serviços externos. Para habilitar Google e envio de e-mail, siga [AUTENTICACAO.md](AUTENTICACAO.md). As credenciais são locais e não estão no Git. A senha Gmail protegida pelo Windows é vinculada ao computador e usuário que a salvou.

## Verificações

```powershell
python manage.py check
python manage.py test core.test_auth core.test_tarefas
```

Os testes usam banco separado e não enviam e-mails reais nem acessam contas Google reais.

## Notificações push e lembretes automáticos

O Timeline permite receber notificações no computador de acordo
com o lembrete selecionado no cadastro ou na edição de uma tarefa.

As opções disponíveis são:

- Sem lembrete.
- No horário da tarefa.
- 30 minutos antes.
- 1 hora antes.
- 1 dia antes.

### Configuração inicial

Instale as dependências e aplique as migrações:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
```

Gere as chaves VAPID no primeiro uso:

```powershell
python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); v.save_key('.env.vapid-private.pem'); v.save_public_key('.env.vapid-public.pem')"
```

As chaves são locais e não devem ser enviadas ao GitHub.
Não gere novas chaves se elas já existirem, pois isso pode
invalidar as inscrições anteriores.

### Executar as notificações

Mantenha dois terminais abertos na pasta do projeto,
com o ambiente virtual ativado.

Terminal 1 - Servidor Django:

```powershell
python manage.py runserver 127.0.0.1:8001 --noreload
```

Terminal 2 - Processo de envio dos lembretes:

```powershell
python manage.py enviar_lembretes --loop
```

O processo verifica os lembretes a cada 30 segundos.

### Como utilizar

1. Acesse o Timeline pelo Google Chrome.
2. Entre na sua conta.
3. Acesse Configurações.
4. Clique em Ativar notificações.
5. Autorize as notificações no navegador.
6. Cadastre uma tarefa com data, horário e lembrete.

As notificações podem ser recebidas mesmo com a aba do
Timeline fechada, desde que o navegador e o sistema
operacional permitam o recebimento.

### Regras de funcionamento

- Tarefas sem lembrete não geram notificações push.
- Tarefas concluídas, não concluídas ou excluídas não geram
  notificações push.
- O sistema registra os lembretes enviados para evitar
  duplicidade por inscrição e horário.
- As inscrições são associadas à conta do usuário.
- O usuário pode desativar as notificações nas Configurações.
- O logout normal do Timeline remove a inscrição associada
  à sessão atual.
- Os lembretes também são considerados nas tarefas recorrentes.
- As notificações internas do Timeline continuam funcionando.

### Requisitos e limitações

A implementação foi desenvolvida e testada no Google Chrome
em computador com Windows. O funcionamento em dispositivos
móveis não foi validado.

O processo de envio deve permanecer ativo, com apenas uma
instância em execução. Lembretes cujo horário passou há mais
de cinco minutos não são recuperados automaticamente.

O navegador e o sistema operacional devem permitir notificações.
Modos como Não Perturbe podem impedir a exibição dos avisos.

A desvinculação foi validada no logout normal do Timeline,
mas não na expiração automática da sessão.

Para implantação em produção, é necessário utilizar HTTPS,
configurar as chaves VAPID no servidor, definir um contato
válido na variável VAPID_SUBJECT e manter o processo de
envio em execução.

### Testes automatizados

Para executar os testes específicos das notificações push:

```powershell
python manage.py test core.test_push
```

Para executar todos os testes do projeto:

```powershell
python manage.py test
```

Na Sprint 11, foram aprovados 77 testes automatizados,
incluindo 11 novos testes relacionados às notificações push.
Os testes simulam o envio sem disparar notificações reais.