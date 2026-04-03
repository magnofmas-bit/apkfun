# constants.py - Constantes globais da aplicação

# ========== UI CONSTANTS ==========
PLACEHOLDER_CHOOSE = "— escolher —"
DEFAULT_PAYMENT_METHOD = "Dinheiro"
DEFAULT_QUANTITY = 1.0
DEFAULT_PRICE = 0.0
DEFAULT_UNIT = "UN"

# ========== CEP VALIDATION ==========
CEP_LENGTH = 8
CEP_API_URL = "https://viacep.com.br/ws/{cep}/json/"
CEP_TIMEOUT = 5

# ========== ERROR MESSAGES ==========
ERROR_CEP_INVALID = "CEP inválido."
ERROR_CEP_NOT_FOUND = "CEP não encontrado."
ERROR_CLIENT_REQUIRED = "Nome obrigatório."
ERROR_PRODUCT_REQUIRED = "Nome do produto obrigatório."
ERROR_PRODUCT_NOT_FOUND = "Produto não encontrado."
ERROR_CLIENT_NOT_FOUND = "Cliente não encontrado."
ERROR_CLIENT_MUST_CHOOSE = "Escolha um cliente."
ERROR_PRODUCT_MUST_CHOOSE = "Escolha um produto."
ERROR_NO_ITEMS = "Nenhum item no pedido"
ERROR_CLIENT_NOT_DEFINED = "Cliente não definido"

# ========== SUCCESS MESSAGES ==========
SUCCESS_CLIENTE_ADDED = "Cliente '{}' adicionado."
SUCCESS_PRODUTO_ADDED = "Produto '{}' adicionado."
SUCCESS_ENDEREÇO_FILLED = "Endereço preenchido!"
SUCCESS_VENDA_FINALIZED = "Venda finalizada!"

# ========== LOG MESSAGES ==========
LOG_RELOAD_ERROR = "Erro reload: {}"
LOG_CEP_ERROR = "Erro CEP: {}"
LOG_CLIENTE_ERROR = "Erro cliente: {}"
LOG_PRODUTO_ERROR = "Erro produto: {}"
LOG_ITEM_ERROR = "Erro item: {}"
LOG_VENDA_ERROR = "Erro venda: {}"

# ========== API STATUS CODES ==========
HTTP_OK = 200

# ========== PAGINATION ==========
DEFAULT_PAGE_SIZE = 50

# ========== DADOS FOLDERS ==========
FOLDER_CLIENTES = "clientes"
FOLDER_PRODUTOS = "produtos"
FOLDER_VENDAS = "vendas"
FOLDER_PDFS = "pdfs"
