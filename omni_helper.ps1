param([string]$Action = "help")

$OMNI_MJS = "C:\Users\Manas\AppData\Roaming\npm\node_modules\omniroute\bin\omniroute.mjs"
$PORT = 20128

function IsRunning {
    $conn = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue
    return ($null -ne $conn)
}

function GetOmniPids {
    $conns = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue
    if ($conns) {
        return $conns | Select-Object -ExpandProperty OwningProcess -Unique
    }
    return @()
}

if ($Action -eq "start") {
    if (IsRunning) {
        Write-Host "OmniRoute already running at http://localhost:$PORT" -ForegroundColor Green
    } else {
        Write-Host "Starting OmniRoute..." -ForegroundColor Cyan
        Start-Process -FilePath "node" -ArgumentList "`"$OMNI_MJS`" serve" -WindowStyle Hidden
        Start-Sleep -Seconds 4
        if (IsRunning) {
            Write-Host "OmniRoute started at http://localhost:$PORT" -ForegroundColor Green
        } else {
            Write-Host "OmniRoute failed to start." -ForegroundColor Red
        }
    }
} elseif ($Action -eq "stop") {
    $pids = GetOmniPids
    if ($pids.Count -gt 0) {
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
        Write-Host "OmniRoute stopped" -ForegroundColor Yellow
    } else {
        Write-Host "OmniRoute was not running" -ForegroundColor Gray
    }
} elseif ($Action -eq "restart") {
    & "$PSScriptRoot\omni_helper.ps1" stop
    Start-Sleep -Seconds 1
    & "$PSScriptRoot\omni_helper.ps1" start
} elseif ($Action -eq "status") {
    if (IsRunning) {
        $pid1 = (GetOmniPids)[0]
        Write-Host "OmniRoute RUNNING  --  http://localhost:$PORT  (PID $pid1)" -ForegroundColor Green
    } else {
        Write-Host "OmniRoute STOPPED  --  run: omni start" -ForegroundColor Red
    }
    Write-Host ""
    omniroute nodes list 2>$null
} else {
    Write-Host ""
    Write-Host "  Usage: omni [start|stop|restart|status|open|nodes]" -ForegroundColor Cyan
    Write-Host ""
}
