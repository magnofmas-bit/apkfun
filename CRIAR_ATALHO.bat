REM ========================================
REM Cria um atalho visual na pasta
REM ========================================

@echo off
setlocal enabledelayedexpansion

echo.
echo Criando atalho para a aplicacao...
echo.

REM Caminho completo do VBS
set "APP_PATH=%~dp0INICIAR.vbs"
set "SHORTCUT_PATH=%~dp0Abrir Controle de Vendas.lnk"

REM Criar atalho usando PowerShell
powershell -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell;" ^
  "$Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%');" ^
  "$Shortcut.TargetPath = '%APP_PATH%';" ^
  "$Shortcut.WorkingDirectory = '%~dp0';" ^
  "$Shortcut.Save();" ^
  "Write-Host 'Atalho criado com sucesso: Abrir Controle de Vendas.lnk'"

echo.
echo Pronto! Voce pode agora clicar duas vezes no arquivo:
echo "Abrir Controle de Vendas.lnk"
echo.
pause
