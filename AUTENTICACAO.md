# Login, Google e recuperação de senha

## Preparar o ambiente

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
if (-not (Test-Path config-autenticacao.local.ps1)) {
    Copy-Item config-autenticacao.example.ps1 config-autenticacao.local.ps1
}
```

Preencha **config-autenticacao.local.ps1** no seu computador. Esse arquivo é ignorado pelo Git. Não coloque credenciais no código ou envie-as pelo chat.

Depois carregue as variáveis e inicie o servidor **na mesma janela do PowerShell**, encerrando o servidor anterior antes:

```powershell
. .\config-autenticacao.local.ps1
python manage.py runserver 127.0.0.1:8001 --noreload
```

## Recuperação de senha por e-mail

O cadastro de aluno pede nome completo, faculdade, data de nascimento, e-mail, usuário e senha. Nome, faculdade e nascimento ficam no perfil do aluno; o e-mail é salvo na conta e usado para enviar o link de recuperação. A data de nascimento não pode estar no futuro. Esses campos não são usados como perguntas de segurança. Contas antigas e o acesso pelo Google continuam válidos, mesmo sem um perfil preenchido.

1. Escolha um serviço de envio por SMTP e obtenha o servidor, porta, usuário e senha de envio. Para Gmail, use uma senha de app, quando disponível na conta; não use sua senha normal do Google.
2. Preencha `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` e `DEFAULT_FROM_EMAIL` com os dados do provedor. O remetente deve ser autorizado por ele.
3. Em geral, a porta 587 usa `EMAIL_USE_TLS=true` e `EMAIL_USE_SSL=false`. Para SSL na porta 465, use TLS false e SSL true. Siga as instruções do seu provedor.
4. Reinicie o servidor, abra `/login/`, clique em **Esqueceu sua senha?** e informe o e-mail de uma conta cadastrada.

O link de recuperação expira em uma hora e só pode ser usado uma vez. A resposta é a mesma para e-mails conhecidos e desconhecidos. Contas criadas somente pelo Google devem entrar pelo Google.

**Sem um serviço de envio configurado**, a recuperação mostra uma mensagem de indisponibilidade e não afirma que enviou o e-mail. Os backends de console, arquivo e descarte não entregam mensagens à caixa de entrada e são bloqueados nesse fluxo. Os testes automatizados usam o backend em memória, sem enviar e-mails reais.

### Envio pelo Gmail

Para a conta remetente `timelinesuporte5@gmail.com`, execute `.\configurar-gmail.ps1` no PowerShell, na pasta do projeto. O script solicita a senha de app sem exibi-la, remove os espaços de agrupamento e a guarda criptografada pelo Windows em `.env.gmail-credential.xml`. Ele cria `.env.gmail-config.ps1` e acrescenta um carregador ao arquivo local existente, preservando todas as linhas anteriores e as credenciais OAuth. Os arquivos `.env.*` são ignorados pelo Git. A credencial protegida só pode ser usada pela mesma conta do Windows no mesmo computador; não deve ser copiada para outra máquina. O script não envia mensagens nem inicia outro servidor: conexão e entrega precisam ser verificadas depois.

Na conta que enviará as mensagens, ative a [Verificação em duas etapas](https://myaccount.google.com/signinoptions/two-step-verification) e depois crie uma [senha de app](https://myaccount.google.com/apppasswords), se esse recurso estiver disponível na conta. Não use a senha normal da conta nem o Client Secret do OAuth.

No arquivo local de configuração já existente, preencha somente as variáveis de e-mail: `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=true`, `EMAIL_USE_SSL=false`, `EMAIL_HOST_USER` com o Gmail remetente, `EMAIL_HOST_PASSWORD` com a senha de app e `DEFAULT_FROM_EMAIL` com `Timeline <o mesmo Gmail remetente>`. Preserve as duas variáveis `GOOGLE_CLIENT_*` existentes. Reinicie o servidor carregando esse arquivo, faça um pedido de recuperação para uma conta com senha local e confirme a entrega na caixa de entrada ou spam. Só considere o envio verificado depois da entrega.

Referências: [senhas de app do Google](https://support.google.com/mail/answer/185833?hl=pt-BR), [servidor SMTP do Gmail](https://developers.google.com/workspace/gmail/imap/imap-smtp).

**Contas antigas:** o cadastro anterior não solicitava e-mail. Para recuperar a senha dessas contas, o administrador precisa cadastrar um endereço legítimo e confirmado no usuário pelo Django Admin. Não adivinhe nem associe automaticamente endereços a contas existentes. Nenhuma conta antiga é alterada por esta implementação.

## Login com Google

1. Crie ou selecione um projeto no [Google Cloud Console](https://console.cloud.google.com/).
2. Em **Google Auth Platform**, configure o nome do aplicativo, público-alvo e e-mail de suporte. Se o aplicativo estiver em teste, inclua os e-mails dos participantes como usuários de teste.
3. Em **Clients/Credenciais**, crie um cliente OAuth do tipo **Aplicativo da Web**.
4. Cadastre exatamente este URI de redirecionamento autorizado:

   `http://127.0.0.1:8001/accounts/google/login/callback/`

   Se usar `localhost`, outra porta ou uma versão publicada, cadastre também o URI correspondente. Em produção, use HTTPS.
5. Copie o ID e o segredo do cliente para `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no arquivo local de configuração.
6. Reinicie o servidor e clique em **Entrar com Google**. Autorize uma conta de teste e confirme que voltou à página Hoje com a conta conectada.

Antes das credenciais serem preenchidas, o botão mostra uma tela informando que o Google ainda não foi ativado. O teste real de autorização só é possível após configurar o projeto no Google.

O aplicativo solicita somente perfil e e-mail. A biblioteca django-allauth faz a troca do código OAuth e valida a identidade, usando proteção de estado e PKCE. Tokens de acesso não são armazenados. O aplicativo não associa automaticamente uma conta Google a uma conta existente só porque os e-mails coincidem; entre com a senha da conta existente nesse caso.

## Verificação

```powershell
python manage.py check
python manage.py test core.test_auth
```

Os testes usam um banco separado e e-mails em memória: não enviam e-mails reais nem contatam o Google. Cobrem recuperação, expiração e reutilização de link, senha divergente, falha de SMTP, cadastro com e-mail, login tradicional, CSRF e início do OAuth com estado e PKCE.

Referências: [recuperação de senha do Django](https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.views.PasswordResetView), [configuração Google no django-allauth](https://docs.allauth.org/en/latest/socialaccount/providers/google.html), [OAuth para aplicações Web do Google](https://developers.google.com/identity/protocols/oauth2/web-server).
