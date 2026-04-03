#!/bin/bash
# =========================================
# SCRIPT BUILD APK - CONTROLE DE VENDAS
# =========================================
# Executa em WSL (Windows Subsystem for Linux)
# Copie o arquivo BUILD_APK.sh para dentro do WSL e execute com: bash BUILD_APK.sh

set -e

PROJECT_DIR="/home/usermagno/Controle_Vendas_App"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "==========================================="
echo "  CONTROLE DE VENDAS - BUILD APK"
echo "  Buildozer em WSL"
echo "==========================================="
echo -e "${NC}"

# ============== FUNÇÃO: Verificar Pré-Requisitos ==============
check_prerequisites() {
    echo -e "\n${YELLOW}[1/5] Verificando pré-requisitos...${NC}"
    
    # Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}  ✓ Python: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}  ✗ Python3 não encontrado${NC}"
        return 1
    fi
    
    # Java
    if command -v java &> /dev/null; then
        echo -e "${GREEN}  ✓ Java: Detectado${NC}"
    else
        echo -e "${RED}  ✗ Java não encontrado${NC}"
        return 1
    fi
    
    # Buildozer
    if python3 -c "import buildozer" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Buildozer: Instalado${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Buildozer não encontrado. Instalando...${NC}"
        pip install buildozer cython android
    fi
    
    echo -e "${GREEN}  ✓ Pré-requisitos verificados${NC}"
    return 0
}

# ============== FUNÇÃO: Verificar Ícones ==============
check_icons() {
    echo -e "\n${YELLOW}[2/5] Verificando ícones...${NC}"
    
    if [ -f "$PROJECT_DIR/data/icon.png" ] && [ -f "$PROJECT_DIR/data/presplash.png" ]; then
        echo -e "${GREEN}  ✓ icon.png encontrado${NC}"
        echo -e "${GREEN}  ✓ presplash.png encontrado${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}  ⚠️  Gerando ícones...${NC}"
    
    if [ -f "$PROJECT_DIR/gerar_icones.py" ]; then
        cd "$PROJECT_DIR"
        python3 gerar_icones.py
        echo -e "${GREEN}  ✓ Ícones gerados!${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Script gerar_icones.py não encontrado${NC}"
        return 1
    fi
}

# ============== FUNÇÃO: Verificar Sintaxe Python ==============
check_python_syntax() {
    echo -e "\n${YELLOW}[3/5] Verificando sintaxe Python...${NC}"
    
    local errors=0
    for file in main.py db.py vendas.py clientes.py constants.py; do
        if [ -f "$PROJECT_DIR/$file" ]; then
            if python3 -m py_compile "$PROJECT_DIR/$file" 2>/dev/null; then
                echo -e "${GREEN}  ✓ $file${NC}"
            else
                echo -e "${RED}  ✗ $file - Erro de sintaxe!${NC}"
                ((errors++))
            fi
        fi
    done
    
    return $errors
}

# ============== FUNÇÃO: Limpar Build Anterior ==============
clean_build_cache() {
    echo -e "\n${YELLOW}[4/5] Limpando cache de build anterior...${NC}"
    
    if [ -d "$PROJECT_DIR/.buildozer" ]; then
        echo -e "${YELLOW}  ⚠️  Removendo .buildozer...${NC}"
        rm -rf "$PROJECT_DIR/.buildozer" || {
            echo -e "${YELLOW}  ⚠️  Não foi possível remover completamente${NC}"
        }
        echo -e "${GREEN}  ✓ Cache limpo${NC}"
    else
        echo -e "${GREEN}  ✓ Nenhum cache anterior${NC}"
    fi
}

# ============== FUNÇÃO: Executar Build ==============
start_build() {
    echo -e "\n${YELLOW}[5/5] Iniciando compilação do APK...${NC}"
    echo -e "${CYAN}Isso pode levar 30-60 minutos na primeira execução...${NC}"
    
    cd "$PROJECT_DIR"
    
    # Ativar venv se existir
    if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
        echo -e "${YELLOW}Ativando venv...${NC}"
        source "$PROJECT_DIR/venv/bin/activate"
    fi
    
    # Limpeza
    echo -e "${YELLOW}Executando: buildozer android clean${NC}"
    buildozer android clean || {
        echo -e "${RED}✗ Erro durante limpeza${NC}"
        return 1
    }
    
    # Build
    echo -e "${YELLOW}Executando: buildozer android debug${NC}"
    if buildozer android debug 2>&1 | tee build_log.txt; then
        echo -e "${GREEN}✓ Build concluído com sucesso!${NC}"
        
        # Verificar APK
        if [ -f "$PROJECT_DIR/bin/"*.apk ]; then
            apk=$(ls -la "$PROJECT_DIR/bin/"*.apk | tail -1)
            echo -e "${GREEN}✓ APK gerado: $apk${NC}"
        fi
        return 0
    else
        echo -e "${RED}✗ Erro durante compilação${NC}"
        return 1
    fi
}

# ============== MAIN ==============
main() {
    # Verificar se projeto existe
    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${RED}✗ Projeto não encontrado em: $PROJECT_DIR${NC}"
        echo -e "${YELLOW}Configure o PROJECT_DIR no script${NC}"
        exit 1
    fi
    
    # Executar verificações
    if ! check_prerequisites; then
        echo -e "${RED}✗ Pré-requisitos não atendidos${NC}"
        exit 1
    fi
    
    if ! check_icons; then
        echo -e "${RED}✗ Ícones não encontrados${NC}"
        exit 1
    fi
    
    if ! check_python_syntax; then
        echo -e "${RED}✗ Erros de sintaxe detectados${NC}"
        exit 1
    fi
    
    clean_build_cache
    
    # Executar build
    if start_build; then
        echo -e "\n${GREEN}"
        echo "==========================================="
        echo "  ✓ BUILD CONCLUÍDO COM SUCESSO!"
        echo "  APK pronto para instalação"
        echo "==========================================="
        echo -e "${NC}"
        exit 0
    else
        echo -e "\n${RED}"
        echo "==========================================="
        echo "  ✗ BUILD FALHOU"
        echo "  Verifique build_log.txt"
        echo "==========================================="
        echo -e "${NC}"
        exit 1
    fi
}

# Executar
main
