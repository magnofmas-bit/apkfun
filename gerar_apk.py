#!/usr/bin/env python3
"""
Script alternativo para gerar APK do Controle de Vendas
Compatível com Windows, Linux e macOS
"""

import os
import sys
import subprocess
import platform

def run_command(cmd, cwd=None):
    """Executa comando e retorna resultado"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd,
                              capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_requirements():
    """Verifica se os requisitos estão instalados"""
    print("🔍 Verificando requisitos...")

    # Python
    python_version = sys.version_info
    if python_version < (3, 8):
        print(f"❌ Python {python_version.major}.{python_version.minor} encontrado. Necessário Python 3.8+")
        return False
    print(f"✅ Python {python_version.major}.{python_version.minor}")

    # Java
    success, out, err = run_command("java -version")
    if not success:
        print("❌ Java não encontrado. Instale OpenJDK 11+")
        return False
    print("✅ Java encontrado")

    # Buildozer
    try:
        import buildozer
        print(f"✅ Buildozer {buildozer.__version__}")
    except ImportError:
        print("❌ Buildozer não encontrado. Execute: pip install buildozer")
        return False

    # python-for-android
    try:
        import p4a
        print("✅ Python-for-Android encontrado")
    except ImportError:
        print("⚠️  Python-for-Android não encontrado. Tentando instalar...")
        run_command("pip install python-for-android")

    return True

def setup_android_sdk():
    """Configura Android SDK se necessário"""
    print("\n📱 Configurando Android SDK...")

    # Verifica se já existe
    android_home = os.environ.get('ANDROID_HOME')
    if android_home and os.path.exists(android_home):
        print(f"✅ Android SDK encontrado em: {android_home}")
        return True

    print("⚠️  Android SDK não encontrado.")
    print("O Buildozer fará download automático durante a compilação.")
    return True

def generate_apk():
    """Gera o APK"""
    print("\n🚀 Iniciando geração do APK...")
    print("Isso pode levar 30-60 minutos dependendo da velocidade da internet.")
    print("Não feche esta janela!\n")

    # Diretório do projeto
    project_dir = os.path.dirname(os.path.abspath(__file__))

    # Comando buildozer
    if platform.system() == 'Windows':
        cmd = 'buildozer android debug'
    else:
        cmd = './buildozer android debug'

    print(f"Executando: {cmd}")
    print("-" * 50)

    # Executa
    success, out, err = run_command(cmd, cwd=project_dir)

    print("-" * 50)

    if success:
        print("✅ APK gerado com sucesso!")
        apk_path = os.path.join(project_dir, 'aplicativo', 'controlevvendas-1.0.0-debug.apk')
        if os.path.exists(apk_path):
            print(f"📱 APK localizado em: {apk_path}")
        else:
            print("📱 Verifique a pasta 'aplicativo' para o arquivo APK")
    else:
        print("❌ Erro durante a geração do APK")
        if err:
            print("Erro detalhado:")
            print(err[-1000:])  # Últimas 1000 caracteres do erro

    return success

def main():
    """Função principal"""
    print("=" * 60)
    print("GERADOR DE APK - CONTROLE DE VENDAS")
    print("=" * 60)
    print("Compatível com Xiaomi Redmi 13C e dispositivos Android modernos")
    print()

    # Verifica requisitos
    if not check_requirements():
        print("\n❌ Requisitos não atendidos. Instale as dependências e tente novamente.")
        input("Pressione Enter para sair...")
        return 1

    # Configura SDK
    if not setup_android_sdk():
        print("\n❌ Problema com Android SDK.")
        input("Pressione Enter para sair...")
        return 1

    # Confirmação
    print("\n" + "=" * 60)
    response = input("Deseja continuar com a geração do APK? (s/n): ")
    if response.lower() not in ['s', 'sim', 'y', 'yes']:
        print("Operação cancelada.")
        return 0

    # Gera APK
    success = generate_apk()

    print("\n" + "=" * 60)
    if success:
        print("🎉 APK GERADO COM SUCESSO!")
        print("Transfira o arquivo .apk para seu celular Xiaomi Redmi 13C")
        print("Habilite 'Instalação de fontes desconhecidas' nas configurações")
    else:
        print("❌ FALHA NA GERAÇÃO DO APK")
        print("Verifique os logs acima para identificar o problema")

    input("\nPressione Enter para sair...")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())