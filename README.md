# apname: Build APK

on:
  push:
    branches: [ "main" ]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Baixar código
      uses: actions/checkout@v3

    - name: Instalar dependências
      run: |
        sudo apt update
        sudo apt install -y python3-pip git zip unzip openjdk-17-jdk
        pip install buildozer

    - name: Rodar Buildozer
      run: |
        buildozer android debug

    - name: Salvar APK
      uses: actions/upload-artifact@v4
      with:
        name: apk
        path: bin/*.apk
