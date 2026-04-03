' ========================================
' Script VBS para iniciar a aplicação
' Controle de Vendas (sem janela visível)
' Processo desacoplado - não encerra com o script
' ========================================

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objShell.CurrentDirectory

' Executar via PowerShell em processo desacoplado
' Usar Python do ambiente virtual
If objFSO.FileExists(strPath & "\.venv\bin\python") Then
    strCmd = "powershell -NoProfile -WindowStyle Hidden -Command ""wsl -e bash -c 'cd /mnt/e/CRIADOS/Controle_Vendas_App && source .venv/bin/activate && python main.py'"""
ElseIf objFSO.FileExists(strPath & "\.venv\Scripts\python.exe") Then
    strCmd = "powershell -NoProfile -WindowStyle Hidden -Command ""Set-Location '" & strPath & "'; .\.venv\Scripts\python.exe main.py"""
Else
    MsgBox "ERRO: Ambiente virtual não encontrado em .venv\bin ou .venv\Scripts.", 16, "Erro"
    WScript.Quit 1
End If

' Executar sem herdar a janela do terminal
objShell.Run strCmd, 0, False

' Mostrar mensagem de sucesso (opcional)
objShell.Popup "Controle de Vendas iniciado! A aplicação está rodando.", 2, "Sistema de Vendas", 64
