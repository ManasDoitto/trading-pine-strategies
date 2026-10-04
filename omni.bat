@echo off
REM ============================================================
REM  omni.bat — OmniRoute control script
REM  Usage: omni start | stop | restart | status | open | nodes
REM ============================================================
SET CMD=%1
IF "%CMD%"=="" SET CMD=help
IF "%CMD%"=="start"   GOTO :start
IF "%CMD%"=="stop"    GOTO :stop
IF "%CMD%"=="restart" GOTO :restart
IF "%CMD%"=="status"  GOTO :status
IF "%CMD%"=="open"    GOTO :open
IF "%CMD%"=="nodes"   GOTO :nodes
GOTO :help

:start
powershell -NoProfile -File "%~dp0omni_helper.ps1" start
GOTO :EOF

:stop
powershell -NoProfile -File "%~dp0omni_helper.ps1" stop
GOTO :EOF

:restart
powershell -NoProfile -File "%~dp0omni_helper.ps1" restart
GOTO :EOF

:status
powershell -NoProfile -File "%~dp0omni_helper.ps1" status
GOTO :EOF

:open
start http://localhost:20128
GOTO :EOF

:nodes
omniroute nodes list
GOTO :EOF

:help
echo.
echo  Usage: omni [command]
echo.
echo  Commands:
echo    start    - Start OmniRoute server (skips if already running)
echo    stop     - Stop OmniRoute server
echo    restart  - Stop then start
echo    status   - Show if running + list provider nodes
echo    open     - Open dashboard in browser (http://localhost:20128)
echo    nodes    - List configured provider nodes
echo.
GOTO :EOF
