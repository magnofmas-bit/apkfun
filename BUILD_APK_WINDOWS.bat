@echo off
REM ========================================
REM SCRIPT DE BUILD APK - CONTROLE DE VENDAS
REM ========================================
REM Executa em PowerShell para melhor compatibilidade
REM Requer: Python 3.8+, Java JDK, Android SDK/NDK

REM Mudar para diretório do projeto
cd /d "%~dp0"

echo.
echo =============================================
echo  CONTROLE DE VENDAS - BUILD APK
echo =============================================
echo.

REM Abrir PowerShell com o script de build
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_APK.ps1"

pause
