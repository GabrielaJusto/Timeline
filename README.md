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
