# Copy to config-autenticacao.local.ps1 and fill in locally.
# Load in PowerShell: . .\config-autenticacao.local.ps1
# Restart the server in that SAME PowerShell window afterwards.
$env:GOOGLE_CLIENT_ID = ""
$env:GOOGLE_CLIENT_SECRET = ""
$env:EMAIL_HOST = ""
$env:EMAIL_PORT = "587"
$env:EMAIL_USE_TLS = "true"
$env:EMAIL_USE_SSL = "false"
$env:EMAIL_HOST_USER = ""
$env:EMAIL_HOST_PASSWORD = ""
$env:DEFAULT_FROM_EMAIL = "Timeline <your-verified-sender@example.com>"
