@echo off
title THE RENDER WAVE - Sample Browser

echo ==========================================
echo   THE RENDER WAVE - Sample Browser
echo   Gradio 6.x - Navegacao por pastas
echo ==========================================
echo.

:: Verificar se Gradio esta instalado
py -c "import gradio" 2> nul
if errorlevel 1 (
    echo [ERRO] Gradio nao encontrado.
    echo A instalar Gradio...
    py -m pip install gradio
    if errorlevel 1 (
        echo [FALHA] Nao foi possivel instalar Gradio.
        pause
        exit /b 1
    )
)

echo Gradio encontrado.
echo A iniciar servidor em http://127.0.0.1:7861
echo.
echo Prima Ctrl+C para terminar.
echo.

:: Abrir browser automaticamente (em background)
timeout /t 2 /nobreak > nul
start "" "http://127.0.0.1:7861"

:: Correr o script Gradio
py "D:\AI_Ecosystem\09_Tools\GUI\batch_engine_gui.py"

pause
