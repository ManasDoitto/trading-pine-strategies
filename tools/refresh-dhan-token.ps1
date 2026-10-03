<#
.SYNOPSIS
  Daily Dhan token refresh, collapsed to one command.

.DESCRIPTION
  Opens Dhan's token page, waits for you to copy the new token to the clipboard, validates it
  LOCALLY (JWT shape + not-already-expired, decoded from the token's own payload - no network
  call needed for this check), then pipes it straight into the VM's `set-token` over SSH.

  The only step this cannot do for you: logging into Dhan and clicking "Generate Access Token" -
  that needs your Dhan session, which nothing outside your own browser should ever handle.

.USAGE
  powershell -File tools\refresh-dhan-token.ps1
  (or just double-click refresh-dhan-token.bat)
#>

$VmHost = "ubuntu@129.225.96.113"
$KeyFile = "$env:USERPROFILE\.ssh\oracle_trading"

function Decode-JwtExpiry($token) {
    $parts = $token.Split('.')
    if ($parts.Count -ne 3) { return $null }
    $payload = $parts[1].Replace('-', '+').Replace('_', '/')
    switch ($payload.Length % 4) { 2 { $payload += '==' } 3 { $payload += '=' } }
    try {
        $json = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload)) | ConvertFrom-Json
        return [DateTimeOffset]::FromUnixTimeSeconds($json.exp).LocalDateTime
    } catch { return $null }
}

Write-Host "Opening Dhan..." -ForegroundColor Cyan
Start-Process "https://web.dhan.co"
Write-Host "`nGo to My Profile -> DhanHQ Trading APIs -> Generate Access Token, then COPY it." -ForegroundColor Yellow
Read-Host "Press Enter once the token is on your clipboard"

$token = (Get-Clipboard -Raw).Trim()
if (-not $token) { Write-Host "Clipboard is empty - nothing to do." -ForegroundColor Red; exit 1 }

$expiry = Decode-JwtExpiry $token
if (-not $expiry) {
    Write-Host "That doesn't look like a Dhan token (not a parseable JWT). Nothing sent." -ForegroundColor Red
    exit 1
}
if ($expiry -le (Get-Date)) {
    Write-Host "That token already expired at $expiry. Nothing sent - copy a fresh one." -ForegroundColor Red
    exit 1
}
Write-Host "Token looks valid, expires $expiry. Sending to the VM..." -ForegroundColor Cyan

$token | & ssh -i $KeyFile $VmHost "set-token"
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDone. The checker/watcher pick this up within one tick - no restart needed." -ForegroundColor Green
} else {
    Write-Host "`nThe VM rejected it or the connection failed - see the message above." -ForegroundColor Red
}
