# 📱 GUIA - COMPILAR APK ANDROID
## Controle de Vendas - Build para Android

---

## ✅ STATUS DA VERIFICAÇÃO

| Item | Status | Descrição |
|------|--------|-----------|
| **Arquivos Python** | ✅ | main.py, db.py, vendas.py, etc. |
| **Configuração Buildozer** | ✅ | buildozer.spec atualizado |
| **Dependências** | ✅ | kivy, requests, pillow, reportlab, bcrypt |
| **Nome Pacote** | ✅ | Corrigido para com.controlevendas |
| **Permissões** | ✅ | Otimizadas para Android |
| **Ícones** | ⚠️ | Necessário executar gerar_icones.py |
| **Pasta data/** | ✅ | Criada |

---

## 🚀 COMO GERAR O APK

### **PASSO 1: Instalar Pré-Requisitos**

```powershell
# Abra o PowerShell como Administrador
# No diretório C:\Controle_Vendas_App

# 1. Instalar dependências Python
pip install --upgrade pip
pip install buildozer cython
pip install kivy requests pillow reportlab bcrypt
```

**Requisitos do Sistema:**
- ✅ Python 3.8 ou superior
- ✅ Java JDK 11+ (OpenJDK recomendado)
- ✅ 8GB RAM e 5GB espaço em disco

### **PASSO 2: Gerar Ícones (Obrigatório)**

```powershell
# No diretório C:\Controle_Vendas_App
python gerar_icones.py
```

**O que faz:**
- Cria `data/icon.png` (192x192)
- Cria `data/presplash.png` (1280x720)

**Se não tiver Python:**
- Crie dois arquivos PNG manualmente:
  - `C:\Controle_Vendas_App\data\icon.png` (mín. 192x192)
  - `C:\Controle_Vendas_App\data\presplash.png` (1280x720)

### **PASSO 3: Preparar e Compilar**

**Opção A: Automático (Recomendado)**
```powershell
python preparar_apk.py
```

**Opção B: Manual**
```powershell
buildozer android debug
```

⏳ **Tempo estimado:** 30-60 minutos na primeira compilação

---

## 📋 CHECKLIST PRÉ-COMPILAÇÃO

Antes de compilar, verifique:

- [ ] Python 3.8+ instalado → `python --version`
- [ ] Java JDK instalado → `java -version`  
- [ ] Buildozer instalado → `pip install buildozer`
- [ ] Arquivo `data/icon.png` existe
- [ ] Arquivo `data/presplash.png` existe
- [ ] Arquivo `buildozer.spec` atualizado
- [ ] Espaço em disco: **5GB mínimo**
- [ ] Pasta `bin/` será criada automaticamente

---

## 📂 ESTRUTURA DO PROJETO

```
C:\Controle_Vendas_App\
├── main.py           ← Entrada da aplicação
├── buildozer.spec    ← Configuração de build
├── requirements.txt  ← Dependências
├── gerar_icones.py   ← Gera ícones
├── preparar_apk.py   ← Prepara build
├── data/             ← NOVO (ícones)
│   ├── icon.png      ← Logo do app
│   └── presplash.png ← Splash screen
├── lib/              ← Módulos Python
├── android/          ← Configuração Android (gerado)
└── bin/              ← APK compilado aqui
    └── controlevendas-1.0.0-debug.apk
```

---

## ✅ CONFIGURAÇÕES JÁ APLICADAS

### buildozer.spec
- ✅ `requirements` = python3, kivy, requests, pillow, reportlab, bcrypt, android
- ✅ `package.name` = controlevendas (sem erro no nome)
- ✅ `package.domain` = com.controlevendas (padronizado)
- ✅ Ícones habilitados: `data/icon.png` e `data/presplash.png`
- ✅ Permissões Android otimizadas (removido WAKE_LOCK)
- ✅ API 34, MinAPI 21, NDK 25b
- ✅ androidx habilitado (Android X)
- ✅ ABI: arm64-v8a + armeabi-v7a

---

## 🔍 ANÁLISE DE COMPATIBILIDADE

### Arquivos Python Verificados ✅
- **main.py** → Kivy UI, sem problemas
- **db.py** → Usa SQLite local (compatível)
- **vendas.py** → Lógica de negócio OK
- **clientes.py** → API ViaCEP (verifica CEP)
- **produtos.py** → Gerenciamento de items
- **pdf_generator.py** → Relatórios PDF
- **constants.py** → Constantes da app

### Observações Importantes ⚠️
1. **Banco de Dados:** Armazenado em `dados/banco.db` (local)
2. **Armazenamento:** Android 11+ usa scoped storage (já funciona)
3. **Permissões:** Internet, arquivo, rede
4. **Backup:** Habilitado (backup em Google Drive)

---

## 🛠️ TROUBLESHOOTING

### "Python não encontrado"
```powershell
# Instalar Python de novo ou adicionar ao PATH
# https://www.python.org/downloads/
```

### "Java não encontrado"  
```powershell
# Instalar OpenJDK
# https://adoptium.net/ (Recomendado)
# Ou: choco install openjdk11 (se tiver Chocolatey)
```

### "Buildozer não encontrado"
```powershell
pip install --upgrade buildozer cython
```

### Build falha com "NDK not found"
```powershell
# Buildozer download automático, mas pode falhar
# Tente limpar cache:
buildozer android clean
buildozer android debug
```

### APK muito grande (>100MB)
- Normal em primeira compilação
- Próximas serão menores (~30-50MB)

---

## 📱 DEPOIS DE GERAR O APK

1. **APK estará em:** `bin/controlevendas-1.0.0-debug.apk`

2. **Instalar em device:**
   ```powershell
   adb install bin/controlevendas-1.0.0-debug.apk
   ```
   
   Ou copiar o arquivo para seu phone

3. **Teste em emulador:**
   ```powershell
   adb install -r bin/controlevendas-1.0.0-debug.apk
   ```

4. **APK Release (para Play Store):**
   ```powershell
   buildozer android release
   ```
   (Requer keystore e configurações adicionais)

---

## 📞 SUPORTE

Se encontrar problemas:

1. Verifique os **logs** na saída do buildozer
2. Tente `buildozer android clean` e gere novamente
3. Atualize Buildozer: `pip install -U buildozer`
4. Verifique espaço em disco (min 5GB)
5. Reinicie o computador

---

## ✨ PRÓXIMAS OTIMIZAÇÕES

- [ ] Gerar icone melhor (atual é azul simples)
- [ ] Configurar keystore para APK release
- [ ] Adicionar analytics/crash reporting
- [ ] Otimizar tamanho do APK
- [ ] Testes automatizados

---

**Status Final:** ✅ **Projeto pronto para compilação!**

Execute: `python preparar_apk.py` ou `buildozer android debug`
