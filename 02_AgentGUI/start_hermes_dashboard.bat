@echo off
setlocal enabledelayedexpansion

cls
echo.
echo  ============================================
echo    HERMES DASHBOARD  -  Windows Launcherecho  ============================================
echo.

REM --- CONFIG ---
set VM_USER=xlybris
set VM_IP=192.168.0.188
set LOCAL_PORT=9119
set VM_PORT=9119
set SSH_KEY=%USERPROFILE%\.ssh\id_ed25519

REM --- Check SSH key ---
if not exist "%SSH_KEY%" (
    echo [ERROR] SSH key not found: %SSH_KEY%
    echo.
    echo  You need to copy the private key from the VM to Windows.
    echo  Steps:
    echo    1. Copy the file to: C:\Users\%USERNAME%\.ssh\id_ed25519
    echo    2. Run this script again.
    echo.
    pause
    exit /b 1
)

REM --- Check server on VM ---
echo [*] Checking Hermes Dashboard status on VM...
ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no -o ConnectTimeout=5 %VM_USER%@%VM_IP% "curl -sf http://127.0.0.1:%VM_PORT%/" >nul 2>&1
if errorlevel 1 (
    echo     Dashboard offline. Starting now...
    ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no -o ConnectTimeout=10 %VM_USER%@%VM_IP% "export PATH=\"/home/%VM_USER%/.local/bin:$PATH\" && nohup hermes dashboard ^> /tmp/hermes_dashboard.log 2^>^&1 ^& sleep 3"
    if errorlevel 1 (
        echo [ERROR] Could not start Hermes Dashboard. Check VM is reachable.
        pause
        exit /b 1
    )
    echo [OK] Hermes Dashboard started
) else (
    echo [OK] Hermes Dashboard is running
)

REM --- Check SSH tunnel ---
echo [*] Checking SSH tunnel...
netstat -an | findstr "127.0.0.1:%LOCAL_PORT%" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     Tunnel closed. Opening...
    start /B ssh -f -N -L %LOCAL_PORT%:127.0.0.1:%VM_PORT% -i "%SSH_KEY%" -o StrictHostKeyChecking=no %VM_USER%@%VM_IP%
    timeout /t 2 /nobreak >nul
    echo [OK] Tunnel open
) else (
    echo [OK] Tunnel already open
)

REM --- Open browser ---
echo [*] Launching browser...
start "" "http://localhost:%LOCAL_PORT%"

REM --- Exit after browser opens ---
exit
