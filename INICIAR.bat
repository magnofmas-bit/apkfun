@echo off
REM ========================================
REM Script para iniciar a aplicação
REM Controle de Vendas
REM ========================================

echo.
echo ========================================
echo    CONTROLE DE VENDAS - Sistema
echo ========================================
echo.
echo Iniciando a aplicação...
echo.

REM Navegar para o diretório da aplicação
cd /d "%~dp0"

REM Verificar se o ambiente virtual do Windows existe
if exist ".venv\Scripts\python.exe" (
    echo Usando ambiente virtual Windows
    call .venv\Scripts\activate.bat
    python main.py
    goto :EOF
)

REM Verificar se o ambiente virtual WSL existe e rodar via WSL
if exist ".venv\bin\python" (
    echo Usando ambiente virtual WSL
    wsl -e bash -c "cd /mnt/e/CRIADOS/Controle_Vendas_App && source .venv/bin/activate && python main.py"
    goto :EOF
)

echo.
echo ERRO: Ambiente virtual não encontrado!
echo Execute "python -m venv .venv" no Windows ou em WSL.
echo.
pause
exit /b 1

REM Se a aplicação fechar com erro
if %errorlevel% neq 0 (
    echo.
    echo ERRO: A aplicação encerrou com erro.
    echo Código de erro: %errorlevel%
    echo.
    pause
)
