# Run in the project folder: .\configurar-gmail.ps1
# The app password is requested privately and encrypted for this Windows user.
$ErrorActionPreference = 'Stop'
$gmailSender = 'timelinesuporte5@gmail.com'
$gmailLocalConfig = Join-Path $PSScriptRoot 'config-autenticacao.local.ps1'
$gmailCredentialFile = Join-Path $PSScriptRoot '.env.gmail-credential.xml'
$gmailConfigFile = Join-Path $PSScriptRoot '.env.gmail-config.ps1'
$gmailLoaderMarker = '# Timeline Gmail configuration (Windows protected credential)'

if (-not (Test-Path -LiteralPath $gmailLocalConfig)) {
    throw 'A configuracao local existente nao foi encontrada. Nenhum arquivo foi alterado.'
}
if ((Test-Path -LiteralPath $gmailCredentialFile) -or (Test-Path -LiteralPath $gmailConfigFile)) {
    throw 'Ja existe uma configuracao Gmail protegida. Nenhum arquivo foi sobrescrito.'
}
$gmailExistingConfig = [System.IO.File]::ReadAllText($gmailLocalConfig)
if ($gmailExistingConfig.Contains($gmailLoaderMarker)) {
    throw 'O carregador Gmail ja esta instalado. Nenhuma alteracao foi feita.'
}

Write-Host 'Configuracao do remetente Timeline: timelinesuporte5@gmail.com'
Write-Host 'Use a senha de app gerada pelo Google. Nao use sua senha normal nem o Client Secret.'
$gmailSecureInput = Read-Host 'Cole a senha de app (ela nao sera exibida)' -AsSecureString
$gmailInputCredential = New-Object System.Management.Automation.PSCredential($gmailSender, $gmailSecureInput)
$gmailPlainAppPassword = $null
try {
    $gmailPlainAppPassword = $gmailInputCredential.GetNetworkCredential().Password -replace '\s', ''
    if ($gmailPlainAppPassword -notmatch '^[A-Za-z0-9]{16}$') {
        throw 'A senha de app deve ter 16 caracteres. Nenhum arquivo foi alterado.'
    }
    $gmailProtectedPassword = ConvertTo-SecureString $gmailPlainAppPassword -AsPlainText -Force
    $gmailCredential = New-Object System.Management.Automation.PSCredential($gmailSender, $gmailProtectedPassword)
} finally {
    $gmailPlainAppPassword = $null
    $gmailInputCredential = $null
    $gmailSecureInput = $null
}

# Export-Clixml uses Windows DPAPI for PSCredential passwords. No plaintext password
# is written to either script. These .env.* files are ignored by the project Git rules.
$gmailCredential | Export-Clixml -LiteralPath $gmailCredentialFile
$gmailCredential = $null
$gmailConfigContent = @'
# Local Gmail configuration. The password is encrypted for the current Windows user.
$env:EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
$env:EMAIL_HOST = 'smtp.gmail.com'
$env:EMAIL_PORT = '587'
$env:EMAIL_USE_TLS = 'true'
$env:EMAIL_USE_SSL = 'false'
$timelineMailCredential = Import-Clixml -LiteralPath (Join-Path $PSScriptRoot '.env.gmail-credential.xml')
$env:EMAIL_HOST_USER = $timelineMailCredential.UserName
$env:EMAIL_HOST_PASSWORD = $timelineMailCredential.GetNetworkCredential().Password
$env:DEFAULT_FROM_EMAIL = 'Timeline <' + $timelineMailCredential.UserName + '>'
$timelineMailCredential = $null
'@
[System.IO.File]::WriteAllText($gmailConfigFile, $gmailConfigContent, (New-Object System.Text.UTF8Encoding($true)))
$gmailLoader = @'

# Timeline Gmail configuration (Windows protected credential)
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env.gmail-config.ps1')) {
    . (Join-Path $PSScriptRoot '.env.gmail-config.ps1')
}
'@
# Append the loader; all existing settings, including Google OAuth, remain intact.
$gmailLoader = [Environment]::NewLine + $gmailLoader + [Environment]::NewLine
[System.IO.File]::AppendAllText($gmailLocalConfig, $gmailLoader, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Configuracao salva. Senha protegida pelo Windows; credenciais OAuth preservadas.'
Write-Host 'O envio ainda nao foi testado. Avise no chat para verificarmos a conexao e reiniciar o servidor.'
