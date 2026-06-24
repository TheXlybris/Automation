@echo off
setlocal enabledelayedexpansion

REM --- CONFIG ---
set VM_USER=xlybris
set VM_IP=192.168.0.188
set LOCAL_PORT=5020
set SSH_KEY=%USERPROFILE%\.ssh\id_ed25519
set PROJECT_DIR=D:\AI_Ecosystem\10_Projects\02_AgentGUI
set MONITOR_PY=%PROJECT_DIR%\tools\windows_monitor.py
set ANIMATOR_PY=%PROJECT_DIR%\engines\image_animator_service.py

REM --- Find Python on Windows ---
set PYTHON_CMD=""
for %%P in (python python3 py) do (
    where /q %%P 2>nul
    if !errorlevel! equ 0 (
        set PYTHON_CMD=%%P
        goto :found_python
    )
)
:found_python
if "%PYTHON_CMD%"=="" (
    echo [WARN] Python not found on Windows PATH.
    echo        Install Python or add it to PATH to enable Windows resource monitoring.
) else (
    echo     Found Python: %PYTHON_CMD%
)

cls
echo.
echo  ============================================
echo    AGENTGUI v2.0  -  Windows Launcherecho  ============================================
echo.

REM --- Check SSH key ---
if not exist "%SSH_KEY%" (
    echo [ERROR] SSH key not found: %SSH_KEY%
    echo.
    echo  You need to copy the private key from the VM to Windows.
    echo  Copy to: C:\Users\%USERNAME%\.ssh\id_ed25519
    echo.
    pause
    exit /b 1
)

REM --- Check server on VM ---
echo [*] Checking AgentGUI server on VM...
ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no -o ConnectTimeout=5 %VM_USER%@%VM_IP% "curl -sf http://127.0.0.1:%LOCAL_PORT%/health" >nul 2>&1
if errorlevel 1 (
    echo     Server offline. Starting now...
    ssh -i "%SSH_KEY%" -o StrictHostKeyChecking=no %VM_USER%@%VM_IP% "nohup /home/%VM_USER%/venv_agentgui/bin/python /media/sf_AI_Ecosystem/10_Projects/02_AgentGUI/server.py > /tmp/agentgui.log 2>&1 & sleep 3"
    if errorlevel 1 (
        echo [ERROR] Could not start server. Check VM is reachable.
        pause
        exit /b 1
    )
    echo [OK] Server started
) else (
    echo [OK] Server is running
)

REM --- Start Windows Resource Monitor ---
echo [*] Checking Windows resource monitor...
if exist "%MONITOR_PY%" (
    REM Check if monitor is already running
    tasklist /FI "WINDOWTITLE eq Windows Resource Monitor" 2>nul | findstr /I "python" >nul
    if errorlevel 1 (
        if "%PYTHON_CMD%"=="" (
            echo [WARN] Python not found. Resource monitor cannot start.
            echo        Install Python to enable Windows resource monitoring.
        ) else (
            echo     Starting Windows resource monitor...
            start "Windows Resource Monitor" /MIN %PYTHON_CMD% "%MONITOR_PY%"
            timeout /t 2 /nobreak >nul
            echo [OK] Windows monitor started
        )
    ) else (
        echo [OK] Windows monitor already running
    )
) else (
    echo [WARN] windows_monitor.py not found at %MONITOR_PY%
)

REM --- Start ImageAnimator GPU Service ---
echo [*] Checking ImageAnimator GPU service...
if exist "%ANIMATOR_PY%" (
    netstat -an | findstr "0.0.0.0:5021" | findstr "LISTENING" >nul
    if errorlevel 1 (
        if "%PYTHON_CMD%"=="" (
            echo [WARN] Python not found. ImageAnimator service cannot start.
            echo        Install Python to enable GPU-accelerated video rendering.
        ) else (
            echo     Starting ImageAnimator GPU service...
            start "ImageAnimator GPU" /MIN %PYTHON_CMD% "%ANIMATOR_PY%"
            timeout /t 2 /nobreak >nul
            echo [OK] ImageAnimator GPU service started
        )
    ) else (
        echo [OK] ImageAnimator GPU service already running
    )
) else (
    echo [WARN] image_animator_service.py not found at %ANIMATOR_PY%
)

REM --- Check SSH tunnel ---
echo [*] Checking SSH tunnel...
netstat -an | findstr "127.0.0.1:%LOCAL_PORT%" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     Tunnel closed. Opening...
    start /B ssh -f -N -L %LOCAL_PORT%:127.0.0.1:%LOCAL_PORT% -i "%SSH_KEY%" -o StrictHostKeyChecking=no %VM_USER%@%VM_IP%
    timeout /t 2 /nobreak >nul
    echo [OK] Tunnel open
) else (
    echo [OK] Tunnel already open
)

REM --- Open browser ---
echo [*] Launching browser...
start "" "http://%VM_IP%:%LOCAL_PORT%"

REM --- Exit after browser opens ---
exit
