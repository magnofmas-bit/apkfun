# 📱 Controle de Vendas

Um aplicativo moderno e robusto para gerenciar vendas, clientes e produtos com interface Kivy.

## ✨ Funcionalidades

- ✅ **Cadastro de Clientes** - Integração automática com ViaCEP
- ✅ **Gerenciamento de Produtos** - Preços variáveis por quantidade
- ✅ **Carrinho de Vendas** - Interface intuitiva para criar pedidos
- ✅ **Geração de Comprovantes** - PDF automático para cada venda
- ✅ **Histórico de Pedidos** - Consulte vendas passadas
- ✅ **Múltiplas Formas de Pagamento** - Dinheiro, PIX, Cheque, Boleto
- ✅ **Backup Automático** - JSON de todas as transações
- ✅ **Banco de Dados Local** - SQLite sem conexão necessária

## 🛠️ Tecnologia

- **Framework**: Kivy 2.3.1
- **Banco de Dados**: SQLite3
- **Linguagem**: Python 3.8+
- **Relatórios**: ReportLab (PDF)
- **API Externa**: ViaCEP (busca de endereços)

## 📦 Instalação

### 1. Clone ou baixe o projeto

```bash
git clone https://github.com/seu-usuario/controle-vendas.git
cd controle-vendas
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Execute a aplicação

```bash
python main.py
```

## 🚀 Início Rápido

### Windows
```powershell
cd C:\Controle_Vendas_App
python main.py
```

### Linux/Mac
```bash
cd ~/Controle_Vendas_App
python main.py
```

## 📱 Compilar para Android

### Instale o Buildozer

```bash
pip install buildozer cython
```

### Gere o APK

```bash
buildozer android debug
```

O APK será criado em `bin/controlevvendas-1.0.0-debug.apk`

## 📁 Estrutura do Projeto

```
controle-vendas/
├── main.py                 # Entrypoint da aplicação
├── app.kv                  # Interface UI
├── db.py                   # Banco de dados
├── vendas.py              # Lógica de vendas
├── clientes.py            # Operações com clientes
├── produtos.py            # Operações com produtos
├── pdf_generator.py       # Geração de comprovantes
├── constants.py           # Constantes globais
├── requirements.txt       # Dependências Python
├── buildozer.spec         # Config do build Android
└── dados/
    ├── banco.db           # SQLite
    ├── clientes/          # Backup JSON
    ├── produtos/          # Backup JSON
    ├── vendas/            # Backup JSON
    └── pdfs/              # Comprovantes
```

## 💾 Banco de Dados

O projeto utiliza **SQLite3** com as seguintes tabelas:

- `clientes` - Dados de clientes
- `produtos` - Catálogo de produtos
- `produto_precos` - Preços variáveis
- `produto_fotos` - Fotos de produtos
- `pedidos` - Histórico de vendas
- `itens_pedido` - Itens por pedido

## 📊 Módulos Principais

### 🔵 main.py
Entrypoint da aplicação com a classe `RootWidget` que gerencia a UI e `VendasApp` que inicia o Kivy.

### 🟡 db.py
Gerenciador de banco de dados SQLite com funções para CRUD e backup JSON automático.

### 🔴 vendas.py
Classe `Venda` que gerencia carrinho de compras e finalização de vendas.

### 🟢 clientes.py
Operações específicas com clientes, incluindo integração com ViaCEP.

### 🔵 produtos.py
Gerenciamento de produtos, preços variáveis, fotos e estoque.

### 🟡 pdf_generator.py
Geração de comprovantes em PDF usando ReportLab.

### 🔴 constants.py
Centraliza todas as constantes da aplicação para fácil manutenção.

## 🔒 Características de Qualidade

- ✅ **Type Hints** - Tipagem completa do código
- ✅ **Logging** - Rastreamento de operações
- ✅ **Tratamento de Erros** - Exceções específicas
- ✅ **Docstrings** - Documentação de funções
- ✅ **Sem Duplicação** - Código limpo e DRY
- ✅ **Constantes Centralizadas** - Fácil customização

## ⚡ Próximas Melhorias

- [ ] Suporte a múltiplas lojas/usuários
- [ ] Dashboard com gráficos de vendas
- [ ] Sincronização em nuvem
- [ ] App mobile em Flutter
- [ ] Integração com sistemas de pagamento
- [ ] Código de barras com câmera

## 🤝 Contribuindo

Contribuições são bem-vindas! Abra uma issue ou pull request.

## 📄 Licença

Este projeto está sob a licença MIT.

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique o arquivo `iniciar o programa.txt`
2. Consulte `ESTRUTURA DO PROJETO.txt`
3. Verifique os logs no console

---

**v1.0.0** - 27/03/2026 | Desenvolvido com ❤️
