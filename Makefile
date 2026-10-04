# OmniRoute control targets
# Usage: make omni-start | omni-stop | omni-status | omni-open | omni-nodes

.PHONY: omni-start omni-stop omni-status omni-open omni-nodes omni-restart

## Start OmniRoute server in the background (safe to run if already running)
omni-start:
	@powershell -NoProfile -Command \
	  "if (Get-NetTCPConnection -LocalPort 20128 -ErrorAction SilentlyContinue) \
	   { Write-Host '✓ OmniRoute already running at http://localhost:20128' } \
	   else { Start-Process node -ArgumentList \
	     '\"C:\Users\Manas\AppData\Roaming\npm\node_modules\omniroute\bin\omniroute.mjs\" serve' \
	     -WindowStyle Hidden; Start-Sleep 3; Write-Host '✓ OmniRoute started at http://localhost:20128' }"

## Stop OmniRoute server
omni-stop:
	@powershell -NoProfile -Command \
	  "Get-NetTCPConnection -LocalPort 20128 -ErrorAction SilentlyContinue | \
	   Select-Object -ExpandProperty OwningProcess -Unique | \
	   ForEach-Object { Stop-Process -Id $$_ -Force -ErrorAction SilentlyContinue }; \
	   Write-Host '✓ OmniRoute stopped'"

## Restart OmniRoute
omni-restart: omni-stop omni-start

## Show running status and provider nodes
omni-status:
	@powershell -NoProfile -Command \
	  "if (Get-NetTCPConnection -LocalPort 20128 -ErrorAction SilentlyContinue) \
	   { Write-Host '● OmniRoute is RUNNING at http://localhost:20128' } \
	   else { Write-Host '○ OmniRoute is STOPPED' }"
	omniroute status 2>NUL
	omniroute nodes list 2>NUL

## Open dashboard in browser
omni-open:
	start http://localhost:20128

## List configured provider nodes
omni-nodes:
	omniroute nodes list
