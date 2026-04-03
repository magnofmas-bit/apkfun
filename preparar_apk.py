#!/usr/bin/env python3
"""
Script de preparação para compilação do APK
Execute: python preparar_apk.py
"""

import os
import sys
import subprocess
import platform

def check_prerequisites():
    """Verifica se todos os pré-requisitos estão instalados"""
    print("=" * 60)
    print("✅ VERIFICAÇÃO DE PRÉ-REQUISITOS")
    print("=" * 60)
    
    problems = []
    
    # 1. Python
    print(f"\n🔍 Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 8):
        problems.append("❌ Python 3.8+ é necessário")
    else:
        print("   ✅ Versão compatible")
    
    # 2. Buildozer
    try:
        import buildozer
        print(f"✅ Buildozer: {buildozer.__version__}")
    except ImportError:
        problems.append("❌ Buildozer não instalado")
        print("❌ Buildozer não encontrado")
    
    # 3. Kivy
    try:
        import kivy
        print(f"✅ Kivy: {kivy.__version__}")
    except ImportError:
        problems.append("⚠️  Kivy não instalado (será instalado pelo Buildozer)")
        print("⚠️  Kivy não encontrado")
    
    # 4. Cython
    try:
        import cython
        print(f"✅ Cython: {cython.__version__}")
    except ImportError:
        problems.append("⚠️  Cython não instalado")
        print("⚠️  Cython não encontrado")
    
    # 5. Java
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Java: Detectado")
        else:
            problems.append("❌ Java não encontrado")
            print("❌ Java não detectado")
    except:
        problems.append("❌ Java não encontrado ou não no PATH")
        print("❌ Java não detectado")
    
    return problems

def check_icon_files():
    """Verifica se ícones existem"""
    print("\n" + "=" * 60)
    print("✅ VERIFICAÇÃO DE ÍCONES")
    print("=" * 60)
    
    icon_path = os.path.join(os.path.dirname(__file__), "data", "icon.png")
    splash_path = os.path.join(os.path.dirname(__file__), "data", "presplash.png")
    
    if os.path.exists(icon_path):
        size = os.path.getsize(icon_path) / 1024
        print(f"✅ icon.png: {size:.1f}KB")
    else:
        print("❌ icon.png não encontrado")
        print("   Execute: python gerar_icones.py")
    
    if os.path.exists(splash_path):
        size = os.path.getsize(splash_path) / 1024
        print(f"✅ presplash.png: {size:.1f}KB")
    else:
        print("❌ presplash.png não encontrado")
        print("   Execute: python gerar_icones.py")

def generate_apk():
    """Gera o APK"""
    print("\n" + "=" * 60)
    print("🚀 INICIANDO COMPILAÇÃO")
    print("=" * 60)
    
    print("\n⏳ Este processo pode levar 30-60 minutos...")
    print("   ⚠️  NÃO FECHE ESTA JANELA!")
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Comando
    if platform.system() == 'Windows':
        cmd = 'buildozer android debug'
    else:
        cmd = 'buildozer android debug'
    
    print(f"\n📦 Comando: {cmd}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, shell=True)
        if result.returncode == 0:
            print("-" * 60)
            print("✅ APK COMPILADO COM SUCESSO!")
            apk_file = os.path.join(project_dir, 'bin', 'controlevendas-1.0.0-debug.apk')
            if os.path.exists(apk_file):
                size = os.path.getsize(apk_file) / (1024*1024)
                print(f"📱 Arquivo: {apk_file}")
                print(f"   Tamanho: {size:.1f}MB")
            else:
                print("📁 Procure pelo APK na pasta 'bin/'")
        else:
            print("-" * 60)
            print("❌ Erro durante compilação")
            print("   Verifique os logs acima")
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    """Função principal"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║  " + "CONTROLE DE VENDAS - PREPARAÇÃO PARA APK".center(54) + "  ║")
    print("║  " + "Android Build Helper".center(54) + "  ║")
    print("╚" + "=" * 58 + "╝")
    
    # 1. Verificar pré-requisitos
    problems = check_prerequisites()
    
    # 2. Verificar ícones
    check_icon_files()
    
    # 3. Mostrar problemas se houver
    if problems:
        print("\n" + "=" * 60)
        print("⚠️  AVISOS E PROBLEMAS")
        print("=" * 60)
        for problem in problems:
            print(f"  {problem}")
    
    # 4. Perguntar se quer continuar
    print("\n" + "=" * 60)
    if problems and any("❌" in p for p in problems):
        print("❌ SOLUCIONE OS PROBLEMAS ACIMA ANTES DE CONTINUAR")
        print("=" * 60)
        sys.exit(1)
    
    response = input("\n🤔 Deseja gerar o APK agora? (s/n): ").strip().lower()
    
    if response in ['s', 'sim', 'y', 'yes']:
        generate_apk()
    else:
        print("\n✅ Preparação concluída!")
        print("   Execute 'python preparar_apk.py' quando estiver pronto")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
