<#
.SYNOPSIS
  Weekly pull of the VM's latest offsite backup down to this laptop - the third copy, outside
  Oracle entirely (survives losing the VM AND the Oracle tenancy, not just the VM).

.DESCRIPTION
  Backups already exist in two places: locally on the VM (/opt/trading/backups/, 30-day retention)
  and offsite in Oracle Object Storage (uploaded nightly). This adds a THIRD copy here, pulled via
  scp over the same SSH key already used for deployment - no new credentials.

  Keeps the last 8 weekly pulls locally (D:\Trading code-Claude\backups_offlaptop), logs every run
  (success or failure) to weekly-backup-pull.log in the same folder, and never deletes a pull it
  can't first confirm is a real, non-empty archive.

.USAGE
  Runs automatically via the "Trading weekly backup pull" scheduled task (Sundays).
  Run by hand any time: powershell -File tools\weekly-backup-pull.ps1
#>

$VmHost = "ubuntu@129.225.96.113"
$KeyFile = "$env:USERPROFILE\.ssh\oracle_trading"
$Dest = "$PSScriptRoot\..\backups_offlaptop"
$LogFile = "$Dest\weekly-backup-pull.log"

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

Log "=== weekly backup pull starting ==="

$latest = & ssh -i $KeyFile $VmHost "ls -t /opt/trading/backups/trading_*.tar.zst 2>/dev/null | head -1"
if (-not $latest) {
    Log "FAILED: no backup file found on the VM (is the nightly backup timer running?)"
    exit 1
}
$latest = $latest.Trim()
$name = Split-Path $latest -Leaf
$localPath = Join-Path $Dest $name

if (Test-Path $localPath) {
    Log "already have $name locally, nothing to pull"
} else {
    & scp -i $KeyFile "${VmHost}:${latest}" $localPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $localPath) -or (Get-Item $localPath).Length -eq 0) {
        Log "FAILED: scp of $name did not produce a valid local file"
        Remove-Item -Force -ErrorAction SilentlyContinue $localPath
        exit 1
    }
    $sizeKb = [math]::Round((Get-Item $localPath).Length / 1KB)
    Log "pulled $name (${sizeKb} KB) -> $localPath"
}

# keep the last 8 weekly pulls, oldest first dropped
$all = Get-ChildItem $Dest -Filter "trading_*.tar.zst" | Sort-Object LastWriteTime -Descending
if ($all.Count -gt 8) {
    $all | Select-Object -Skip 8 | ForEach-Object {
        Remove-Item $_.FullName -Force
        Log "pruned old local copy $($_.Name)"
    }
}

Log "=== weekly backup pull done ==="
