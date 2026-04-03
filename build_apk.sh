#!/bin/bash
cd /mnt/e/CRIADOS/Controle_Vendas_App

echo "=== Python Version ===" 
python3 --version

echo "=== Removendo venv antigo ==="
rm -rf .venv-buildozer

echo "=== Criando novo venv ==="
python3 -m venv .venv-buildozer

echo "=== Ativando venv ==="
source .venv-buildozer/bin/activate

echo "=== Instalando pip/setuptools/wheel ==="
pip install --upgrade pip setuptools wheel

echo "=== Instalando buildozer e cython ==="
pip install buildozer cython

echo "=== Iniciando build do APK ===" 
buildozer --storage-dir=/home/usermagno/.buildozer_store android debug

echo "=== Finalizando ==="
ls -lh ./aplicativo/*.apk 2>/dev/null || echo "APK não encontrado em aplicativo/"
exit 0
