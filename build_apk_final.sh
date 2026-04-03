#!/bin/bash
set -e

cd /mnt/e/CRIADOS/Controle_Vendas_App

echo "================================"
echo "BUILD APK - CONTROLE DE VENDAS"
echo "================================"
echo ""

echo "1. Verificando Python..."
python3 --version
echo ""

echo "2. Criando virtualenv..."
python3 -m venv .venv-buildozer
source .venv-buildozer/bin/activate
echo "✓ Virtualenv ativado"
echo ""

echo "3. Instalando dependências..."
pip install --upgrade pip setuptools wheel -q
pip install buildozer cython -q
echo "✓ Dependências instaladas"
echo ""

echo "4. Limpando build antigo..."
rm -rf .buildozer 2>/dev/null || true
echo "✓ Limpeza feita"
echo ""

echo "5. Iniciando build do APK (pode levar 10-30 minutos)..."
buildozer --storage-dir=/home/usermagno/.buildozer_store android release

echo ""
echo "================================"
echo "BUILD FINALIZADO!"
echo "================================"

echo ""
echo "6. Localizando APK..."
APK_PATH=$(find .buildozer -name "*debug*.apk" -type f 2>/dev/null | head -1)
if [ -n "$APK_PATH" ]; then
    echo "✓ APK encontrado em: $APK_PATH"
    echo ""
    echo "7. Copiando para aplicativo/..."
    mkdir -p ./aplicativo
    cp "$APK_PATH" ./aplicativo/
    APP_NAME=$(basename "$APK_PATH")
    echo "✓ APK copiado: ./aplicativo/$APP_NAME"
    echo ""
    ls -lh ./aplicativo/
else
    echo "⚠ APK não encontrado. Verifique o log do build."
    exit 1
fi

echo ""
echo "================================"
echo "✓ APK PRONTO PARA INSTALAR!"
echo "================================"
