# =========================================
# SCRIPT BUILD APK - CONTROLE DE VENDAS
# =========================================
# Execute: powershell -ExecutionPolicy Bypass -File BUILD_APK.ps1

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path $MyInvocation.MyCommand.Path -Parent

Write-Host "
╔════════════════════════════════════════════╗
║   CONTROLE DE VENDAS - BUILD APK          ║
║   Executando diagnóstico e compilação      ║
╚════════════════════════════════════════════╝
" -ForegroundColor Cyan

# ============== FUNÇÃO: Verificar Pré-Requisitos ==============
function Test-Prerequisites {
    Write-Host "`n[1/5] Verificando pré-requisitos..." -ForegroundColor Yellow
    
    $missing = @()
    
    # Verificar Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green
    } catch {
        $missing += "Python 3.8+"
        Write-Host "  ✗ Python não encontrado" -ForegroundColor Red
    }
    
    # Verificar Java
    try {
        $javaVersion = java -version 2>&1
        if ($javaVersion -match "version") {
            Write-Host "  ✓ Java: Instalado" -ForegroundColor Green
        }
    } catch {
        $missing += "Java JDK"
        Write-Host "  ✗ Java não encontrado" -ForegroundColor Red
    }
    
    # Verificar Buildozer
    try {
        python -c "import buildozer; print(buildozer.__version__)" | Out-Null
        Write-Host "  ✓ Buildozer: Instalado" -ForegroundColor Green
    } catch {
        $missing += "Buildozer"
        Write-Host "  ✗ Buildozer não encontrado" -ForegroundColor Red
    }
    
    if ($missing.Count -gt 0) {
        Write-Host "`n⚠️  AVISO: Faltam dependências:" -ForegroundColor Yellow
        foreach ($dep in $missing) {
            Write-Host "   - $dep" -ForegroundColor Yellow
        }
        Write-Host "`nInstalando dependências..." -ForegroundColor Yellow
        try {
            python -m pip install --upgrade pip buildozer cython
            Write-Host "✓ Dependências instaladas!" -ForegroundColor Green
        } catch {
            Write-Host "✗ Erro ao instalar dependências" -ForegroundColor Red
            return $false
        }
    }
    
    return $true
}

# ============== FUNÇÃO: Verificar Ícones ==============
function Test-Icons {
    Write-Host "`n[2/5] Verificando ícones..." -ForegroundColor Yellow
    
    $iconPath = "$ProjectDir\data\icon.png"
    $splashPath = "$ProjectDir\data\presplash.png"
    
    $iconExists = Test-Path $iconPath
    $splashExists = Test-Path $splashPath
    
    if ($iconExists -and $splashExists) {
        Write-Host "  ✓ icon.png encontrado" -ForegroundColor Green
        Write-Host "  ✓ presplash.png encontrado" -ForegroundColor Green
        return $true
    }
    
    Write-Host "  ⚠️  Gerando ícones..." -ForegroundColor Yellow
    
    if (Test-Path "$ProjectDir\gerar_icones.py") {
        try {
            python "$ProjectDir\gerar_icones.py"
            Write-Host "  ✓ Ícones gerados!" -ForegroundColor Green
            return $true
        } catch {
            Write-Host "  ✗ Erro ao gerar ícones" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "  ✗ Script gerar_icones.py não encontrado" -ForegroundColor Red
        return $false
    }
}

# ============== FUNÇÃO: Verificar Sintaxe Python ==============
function Test-PythonSyntax {
    Write-Host "`n[3/5] Verificando sintaxe Python..." -ForegroundColor Yellow
    
    $pyFiles = @("main.py", "db.py", "vendas.py", "clientes.py", "constants.py")
    $errors = @()
    
    foreach ($file in $pyFiles) {
        $fullPath = "$ProjectDir\$file"
        if (Test-Path $fullPath) {
            try {
                python -m py_compile $fullPath 2>&1 | Out-Null
                Write-Host "  ✓ $file" -ForegroundColor Green
            } catch {
                $errors += $file
                Write-Host "  ✗ $file - Erro de sintaxe!" -ForegroundColor Red
            }
        }
    }
    
    return $errors.Count -eq 0
}

# ============== FUNÇÃO: Limpar Build Anterior ==============
function Clean-BuildCache {
    Write-Host "`n[4/5] Limpando cache de build anterior..." -ForegroundColor Yellow
    
    $buildDir = "$ProjectDir\.buildozer"
    
    if (Test-Path $buildDir) {
        Write-Host "  ⚠️  Removendo diretório .buildozer (isso pode levar um tempo)..." -ForegroundColor Yellow
        try {
            Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  ✓ Cache limpo!" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠️  Não foi possível limpar completamente (continuar mesmo assim)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ✓ Nenhum cache anterior encontrado" -ForegroundColor Green
    }
}

# ============== FUNÇÃO: Executar Build ==============
function Start-Build {
    Write-Host "`n[5/5] Iniciando compilação do APK..." -ForegroundColor Yellow
    Write-Host "Isso pode levar 30-60 minutos na primeira execução..." -ForegroundColor Cyan
    Write-Host ""
    
    Set-Location $ProjectDir
    
    Write-Host "Executando: buildozer android clean" -ForegroundColor Gray
    buildozer android clean
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n✗ Erro durante limpeza do build" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`nExecutando: buildozer android debug" -ForegroundColor Gray
    buildozer android debug 2>&1 | Tee-Object -FilePath "build_log.txt"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Build concluído com sucesso!" -ForegroundColor Green
        if (Test-Path "$ProjectDir\bin\*.apk") {
            $apk = Get-ChildItem "$ProjectDir\bin\*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($apk) {
                Write-Host "✓ APK gerado: $($apk.FullName)" -ForegroundColor Green
                Write-Host "  Tamanho: $([math]::Round($apk.Length / 1MB, 2)) MB" -ForegroundColor Green
            }
        }
        return $true
    } else {
        Write-Host "`n✗ Erro durante compilação" -ForegroundColor Red
        Write-Host "Verifique build_log.txt para detalhes" -ForegroundColor Yellow
        return $false
    }
}

# ============== MAIN ==============
try {
    # Executar verificações
    if (-not (Test-Prerequisites)) {
        throw "Pré-requisitos não atendidos"
    }
    
    if (-not (Test-Icons)) {
        throw "Ícones não encontrados ou não puderam ser gerados"
    }
    
    if (-not (Test-PythonSyntax)) {
        throw "Erros de sintaxe detectados em arquivos Python"
    }
    
    Clean-BuildCache
    
    # Executar build
    $buildSuccess = Start-Build
    
    if ($buildSuccess) {
        Write-Host "`n
╔════════════════════════════════════════════╗
║   ✓ BUILD CONCLUÍDO COM SUCESSO!         ║
║   APK pronto para instalação              ║
╚════════════════════════════════════════════╝
" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`n
╔════════════════════════════════════════════╗
║   ✗ BUILD FALHOU                         ║
║   Verifique build_log.txt                 ║
╚════════════════════════════════════════════╝
" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "`n✗ ERRO: $_" -ForegroundColor Red
    exit 1
}
