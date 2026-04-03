"""
db.py - Módulo de gestão de banco de dados SQLite e backup JSON.
Centraliza todas as operações de banco de dados, criação de tabelas e consultas.
"""

import sqlite3
import os
from datetime import datetime
import json
from typing import List, Dict, Optional, Any
import logging
import bcrypt
from contextlib import contextmanager

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# 📁 CAMINHO DO BANCO + PASTAS
# =========================
def get_base_dir() -> str:
    """Retorna o diretório base da aplicação."""
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir() -> str:
    """Cria e retorna o diretório de dados, criando subpastas se necessário."""
    base_dir = get_base_dir()
    data_dir = os.path.join(base_dir, "dados")

    # Criar diretórios
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "clientes"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "produtos"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "vendas"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "pdfs"), exist_ok=True)

    return data_dir


def get_db_path() -> str:
    """Retorna o caminho do banco de dados SQLite."""
    return os.path.join(get_data_dir(), "banco.db")


# =========================
# 🔌 POOL DE CONEXÕES
# =========================
class DatabasePool:
    """Pool de conexões SQLite para melhor performance e gerenciamento."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.pool = []
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializa o pool de conexões."""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Habilitar foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            self.pool.append(conn)
    
    @contextmanager
    def get_conn(self):
        """Retorna uma conexão do pool de forma thread-safe."""
        if not self.pool:
            # Se pool vazio, criar nova conexão temporária
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = self.pool.pop()
            try:
                yield conn
            finally:
                self.pool.append(conn)


# Instância global do pool
_db_pool = None

def get_db_pool() -> DatabasePool:
    """Retorna a instância global do pool de conexões."""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool(get_db_path())
    return _db_pool


# =========================
# 🔌 CONEXÃO (LEGACY - PARA COMPATIBILIDADE)
# =========================
def get_conn() -> sqlite3.Connection:
    """
    Retorna uma conexão do pool para uso legado.
    IMPORTANTE: Você deve fechar a conexão quando terminar com conn.close()
    Melhor usar 'with get_db_pool().get_conn() as conn:' em código novo.
    """
    pool = get_db_pool()
    if not pool.pool:
        # Se pool vazio, criar nova conexão temporária
        conn = sqlite3.connect(pool.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    else:
        # Pegar conexão do pool (SEM usar context manager para compatibilidade)
        return pool.pool.pop() if pool.pool else None

# =========================
# 🧱 CRIAR TABELAS
# =========================
def init_db():
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            endereco TEXT,
            numero TEXT,
            bairro TEXT,
            cidade TEXT,
            cep TEXT,
            criado_em TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo_barras TEXT,
            unidade TEXT,
            preco REAL DEFAULT 0,
            estoque REAL DEFAULT 0,
            criado_em TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS produto_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            caminho TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS produto_precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            quantidade_min REAL,
            preco REAL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_client_id TEXT,
            cliente_id INTEGER,
            cliente_nome TEXT,
            valor_total REAL,
            data_pedido TEXT,
            status TEXT DEFAULT 'pending',
            json_payload TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            produto_id INTEGER,
            produto_nome TEXT,
            quantidade REAL,
            preco_unitario REAL,
            total REAL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,  -- Alterado para senha_hash
            nome_completo TEXT,
            usa_biometria INTEGER DEFAULT 0,
            criado_em TEXT,
            -- Campos adicionais opcionais
            cpf TEXT,
            rg TEXT,
            cep TEXT,
            endereco TEXT,
            numero TEXT,
            complemento TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            foto TEXT,
            atualizado_em TEXT
        )
        """)

        # Criar índices para melhor performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_itens_pedido ON itens_pedido(pedido_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email)")

        # Migração: adicionar campos opcionais se não existirem
        try:
            # Verificar se os campos já existem
            cur.execute("PRAGMA table_info(usuarios)")
            columns = [row[1] for row in cur.fetchall()]
            
            campos_adicionar = [
                ('cpf', 'TEXT'),
                ('rg', 'TEXT'),
                ('cep', 'TEXT'),
                ('endereco', 'TEXT'),
                ('numero', 'TEXT'),
                ('complemento', 'TEXT'),
                ('bairro', 'TEXT'),
                ('cidade', 'TEXT'),
                ('estado', 'TEXT'),
                ('foto', 'TEXT'),
                ('atualizado_em', 'TEXT')
            ]
            
            for campo, tipo in campos_adicionar:
                if campo not in columns:
                    cur.execute(f"ALTER TABLE usuarios ADD COLUMN {campo} {tipo}")
                    logger.info(f"Campo '{campo}' adicionado à tabela usuarios")
        except sqlite3.Error as e:
            logger.warning(f"Erro na migração de campos: {e}")

        # Migração: adicionar campo estoque à tabela produtos se não existir
        try:
            cur.execute("PRAGMA table_info(produtos)")
            columns_produtos = [row[1] for row in cur.fetchall()]
            
            if 'estoque' not in columns_produtos:
                cur.execute("ALTER TABLE produtos ADD COLUMN estoque REAL DEFAULT 0")
                logger.info("Campo 'estoque' adicionado à tabela produtos")
        except sqlite3.Error as e:
            logger.warning(f"Erro na migração de produtos: {e}")

        # Migração: migrar senhas para hash se necessário
        try:
            cur.execute("PRAGMA table_info(usuarios)")
            columns = [row[1] for row in cur.fetchall()]
            
            if 'senha' in columns and 'senha_hash' not in columns:
                # Renomear coluna senha para senha_hash
                cur.execute("ALTER TABLE usuarios RENAME COLUMN senha TO senha_hash")
                logger.info("Coluna 'senha' renomeada para 'senha_hash'")
                
                # Migrar senhas existentes para hash
                cur.execute("SELECT id, senha_hash FROM usuarios WHERE senha_hash IS NOT NULL")
                usuarios = cur.fetchall()
                for usuario in usuarios:
                    if usuario['senha_hash'] and not usuario['senha_hash'].startswith('$2b$'):
                        # Senha não está hasheada, fazer hash
                        hashed = bcrypt.hashpw(usuario['senha_hash'].encode(), bcrypt.gensalt())
                        cur.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", 
                                  (hashed.decode(), usuario['id']))
                        logger.info(f"Senha do usuário ID {usuario['id']} migrada para hash")
        except sqlite3.Error as e:
            logger.warning(f"Erro na migração de senhas: {e}")

        conn.commit()

# =========================
# 👤 CLIENTES
# =========================
def add_cliente(data: Dict[str, Any]) -> int:
    """
    Adiciona um novo cliente ao banco de dados.
    
    Args:
        data: Dicionário com chaves (nome, telefone, endereco, bairro, cidade, cep)
    
    Returns:
        int: ID do cliente criado
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO clientes (nome, telefone, endereco, numero, bairro, cidade, cep, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("nome"),
            data.get("telefone"),
            data.get("endereco"),
            data.get("numero"),
            data.get("bairro"),
            data.get("cidade"),
            data.get("cep"),
            datetime.now().isoformat()
        ))

        conn.commit()
        cliente_id = cur.lastrowid
        salvar_backup("clientes", cliente_id, data)
        return cliente_id


def list_clientes() -> List[Dict]:
    """Retorna lista de todos os clientes ordenados por nome."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM clientes ORDER BY nome")
        rows = [dict(r) for r in cur.fetchall()]
        return rows

# =========================
# 📦 PRODUTOS
# =========================
def add_produto(data: Dict[str, Any]) -> int:
    """
    Adiciona um novo produto ao banco de dados.
    
    Args:
        data: Dicionário com chaves (nome, codigo_barras, unidade, preco)
    
    Returns:
        int: ID do produto criado
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO produtos (nome, codigo_barras, unidade, preco, estoque, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("nome"),
            data.get("codigo_barras"),
            data.get("unidade"),
            float(data.get("preco", 0)),
            float(data.get("estoque", 0)),
            datetime.now().isoformat()
        ))

        conn.commit()
        produto_id = cur.lastrowid
        salvar_backup("produtos", produto_id, data)
        return produto_id


def list_produtos() -> List[Dict]:
    """Retorna lista de todos os produtos ordenados por nome."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM produtos ORDER BY nome")
        rows = [dict(r) for r in cur.fetchall()]
        return rows

# =========================
# 🧾 PEDIDOS
# =========================
def salvar_pedido_local(pedido_payload: Dict[str, Any], itens: List[Dict]) -> int:
    """
    Salva um pedido e seus itens no banco de dados.
    
    Args:
        pedido_payload: Dicionário com dados do pedido
        itens: Lista de dicionários com dados dos itens
    
    Returns:
        int: ID do pedido criado
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        data_pedido = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calcular valor total com segurança
        valor_total = 0.0
        for item in itens:
            try:
                valor_total += float(item.get("total", 0))
            except (ValueError, TypeError):
                pass

        pedido_client_id = pedido_payload.get("pedido_client_id") or f"local-{int(datetime.now().timestamp())}"

        cur.execute("""
            INSERT INTO pedidos (pedido_client_id, cliente_id, cliente_nome, valor_total, data_pedido, status, json_payload)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            pedido_client_id,
            pedido_payload.get("cliente_id"),
            pedido_payload.get("cliente_nome"),
            valor_total,
            data_pedido,
            json.dumps(pedido_payload, ensure_ascii=False)
        ))

        pedido_id = cur.lastrowid

        # Inserir itens do pedido
        for it in itens:
            cur.execute("""
                INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, quantidade, preco_unitario, total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pedido_id,
                it.get("produto_id"),
                it.get("produto_nome"),
                float(it.get("quantidade", 0)),
                float(it.get("preco_unitario", 0)),
                float(it.get("total", 0))
            ))

        conn.commit()

        # Salvar backup JSON
        salvar_backup("vendas", pedido_id, {
            "pedido": pedido_payload,
            "itens": itens,
            "valor_total": valor_total
        })

        return pedido_id

# =========================
# 📊 CONSULTAS
# =========================
def list_pedidos(status: Optional[str] = None) -> List[Dict]:
    """
    Retorna lista de pedidos, opcionalmente filtrado por status.
    
    Args:
        status: Status do pedido para filtro (ex: 'pending', 'completed'), None retorna todos
    
    Returns:
        List[Dict]: Lista de pedidos
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        if status:
            cur.execute("SELECT * FROM pedidos WHERE status=? ORDER BY id DESC", (status,))
        else:
            cur.execute("SELECT * FROM pedidos ORDER BY id DESC")

        rows = [dict(r) for r in cur.fetchall()]
        return rows


def get_itens_pedido(pedido_id: int) -> List[Dict]:
    """Retorna itens de um pedido específico."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM itens_pedido WHERE pedido_id=?", (pedido_id,))
        rows = [dict(r) for r in cur.fetchall()]
        return rows
def update_pedido_status(pedido_id: int, status: str, extra_payload: Optional[Dict] = None) -> bool:
    """
    Atualiza o status de um pedido.
    
    Args:
        pedido_id: ID do pedido
        status: Novo status
        extra_payload: Dados adicionais para salvar no JSON
    
    Returns:
        bool: True se atualizado com sucesso
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        if extra_payload is None:
            cur.execute("UPDATE pedidos SET status=? WHERE id=?", (status, pedido_id))
        else:
            cur.execute("""
                UPDATE pedidos 
                SET status=?, json_payload=? 
                WHERE id=?
            """, (status, json.dumps(extra_payload, ensure_ascii=False), pedido_id))

        conn.commit()
        return True

# =========================
# 💾 BACKUP JSON
# =========================
def salvar_backup(tipo: str, id_: int, dados: Dict[str, Any]) -> bool:
    """
    Salva dados em arquivo JSON como backup.
    
    Para produtos: Salva em arquivo consolidado produtos.json
    Outros tipos: Salva arquivo individual por ID
    
    Args:
        tipo: Tipo do backup (clientes, produtos, vendas)
        id_: ID do item sendo salvo
        dados: Dados a serem salvos
    
    Returns:
        bool: True se salvo com sucesso
    """
    pasta = os.path.join(get_data_dir(), tipo)
    
    try:
        # Produtos: sempre consolidados em um arquivo único
        if tipo == "produtos":
            caminho = os.path.join(pasta, "produtos.json")
            
            # Ler arquivo existente ou criar novo
            if os.path.exists(caminho):
                with open(caminho, "r", encoding="utf-8") as f:
                    dados_consolidados = json.load(f)
            else:
                dados_consolidados = {"produtos": []}
            
            # Adicionar ID aos dados se não existir
            dados_com_id = dados.copy()
            dados_com_id["id"] = id_
            
            # Atualizar ou adicionar produto
            produtos = dados_consolidados.get("produtos", [])
            encontrou = False
            for i, p in enumerate(produtos):
                if p.get("id") == id_:
                    produtos[i] = dados_com_id
                    encontrou = True
                    break
            
            if not encontrou:
                produtos.append(dados_com_id)
            
            dados_consolidados["produtos"] = produtos
            
            # Salvar arquivo consolidado
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados_consolidados, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Produto {id_} salvo em {caminho}")
            return True
        else:
            # Outros tipos: arquivo individual por ID (comportamento original)
            caminho = os.path.join(pasta, f"{id_}.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            return True
            
    except (IOError, OSError) as e:
        logger.error(f"Erro ao salvar backup ({tipo}/{id_}): {e}")
        return False


# =========================
# 👤 USUÁRIOS
# =========================
def add_usuario(username: str, email: str, senha: str, nome_completo: str = "", usa_biometria: bool = False,
               cpf: str = "", rg: str = "", cep: str = "", endereco: str = "", numero: str = "", 
               complemento: str = "", bairro: str = "", cidade: str = "", estado: str = "", 
               foto: str = "") -> Dict[str, Any]:
    """
    Cria um novo usuário no sistema.
    
    Args:
        username: Nome de usuário único
        email: Email do usuário para recuperação de senha
        senha: Senha do usuário (será hasheada)
        nome_completo: Nome completo do usuário (opcional)
        usa_biometria: Se True, permite autenticação por digital
        cpf, rg, cep, endereco, numero, complemento, bairro, cidade, estado, foto: Campos opcionais
    
    Returns:
        Dict com resultado (sucesso, mensagem, usuario_id)
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        if not username or not email or not senha:
            return {"sucesso": False, "mensagem": "Usuário, email e senha obrigatórios"}

        # Hash da senha
        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

        cur.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
        if cur.fetchone():
            return {"sucesso": False, "mensagem": "Usuário já existe"}

        cur.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        if cur.fetchone():
            return {"sucesso": False, "mensagem": "Email já está registrado"}

        cur.execute("""
            INSERT INTO usuarios (username, email, senha_hash, nome_completo, usa_biometria, criado_em,
                                cpf, rg, cep, endereco, numero, complemento, bairro, cidade, estado, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            email,
            senha_hash.decode(),  # Armazenar como string
            nome_completo,
            1 if usa_biometria else 0,
            datetime.now().isoformat(),
            cpf, rg, cep, endereco, numero, complemento, bairro, cidade, estado, foto
        ))

        conn.commit()
        usuario_id = cur.lastrowid
        return {"sucesso": True, "mensagem": "Usuário criado com sucesso", "usuario_id": usuario_id}


def verificar_login(username: str, senha: str) -> Dict[str, Any]:
    """
    Verifica credenciais de login.
    
    Args:
        username: Nome de usuário
        senha: Senha do usuário
    
    Returns:
        Dict com resultado (sucesso, mensagem, usuario)
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, username, nome_completo, senha_hash FROM usuarios 
            WHERE username = ?
        """, (username,))
        
        user = cur.fetchone()
        if user and bcrypt.checkpw(senha.encode(), user['senha_hash'].encode()):
            return {
                "sucesso": True,
                "mensagem": "Login bem-sucedido",
                "usuario": {
                    "id": user['id'],
                    "username": user['username'],
                    "nome_completo": user['nome_completo']
                }
            }
        else:
            return {"sucesso": False, "mensagem": "Usuário ou senha incorretos"}


def usuario_existe(username: str) -> bool:
    """Verifica se um usuário já existe."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
        return bool(cur.fetchone())


def verificar_biometria_habilitada(username: str) -> bool:
    """Verifica se o usuário tem autenticação por digital habilitada."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT usa_biometria FROM usuarios WHERE username = ?", (username,))
        resultado = cur.fetchone()
        return bool(resultado[0]) if resultado else False


def atualizar_biometria_usuario(username: str, usa_biometria: bool) -> Dict[str, Any]:
    """Atualiza o status de biometria de um usuário existente."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            "UPDATE usuarios SET usa_biometria = ? WHERE username = ?",
            (1 if usa_biometria else 0, username)
        )
        conn.commit()
        
        if cur.rowcount > 0:
            msg = "Autenticação por digital habilitada" if usa_biometria else "Autenticação por digital desabilitada"
            logger.info(f"Usuário '{username}': {msg}")
            return {"sucesso": True, "mensagem": msg}
        else:
            logger.warning(f"Usuário '{username}' não encontrado para atualizar biometria")
            return {"sucesso": False, "mensagem": "Usuário não encontrado"}


def atualizar_usuario(usuario_id: int, username: str = None, email: str = None, senha: str = None,
                     nome_completo: str = None, usa_biometria: bool = None, cpf: str = None, rg: str = None,
                     cep: str = None, endereco: str = None, numero: str = None, complemento: str = None,
                     bairro: str = None, cidade: str = None, estado: str = None, foto: str = None) -> Dict[str, Any]:
    """
    Atualiza dados do usuário.
    
    Args:
        usuario_id: ID do usuário a ser atualizado
        Campos opcionais: username, email, senha, nome_completo, usa_biometria, cpf, rg, cep, endereco, numero, complemento, bairro, cidade, estado, foto
    
    Returns:
        Dict com resultado (sucesso, mensagem)
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        # Verificar se usuário existe
        cur.execute("SELECT id FROM usuarios WHERE id = ?", (usuario_id,))
        if not cur.fetchone():
            return {"sucesso": False, "mensagem": "Usuário não encontrado"}

        # Verificar se email já existe para outro usuário
        if email:
            cur.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", (email, usuario_id))
            if cur.fetchone():
                return {"sucesso": False, "mensagem": "Email já está sendo usado por outro usuário"}

        # Verificar se username já existe para outro usuário
        if username:
            cur.execute("SELECT id FROM usuarios WHERE username = ? AND id != ?", (username, usuario_id))
            if cur.fetchone():
                return {"sucesso": False, "mensagem": "Nome de usuário já está sendo usado"}

        # Construir query de atualização dinâmica
        campos = []
        valores = []

        if username is not None:
            campos.append("username = ?")
            valores.append(username)
        if email is not None:
            campos.append("email = ?")
            valores.append(email)
        if senha is not None:
            campos.append("senha_hash = ?")
            senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())
            valores.append(senha_hash.decode())
        if nome_completo is not None:
            campos.append("nome_completo = ?")
            valores.append(nome_completo)
        if usa_biometria is not None:
            campos.append("usa_biometria = ?")
            valores.append(1 if usa_biometria else 0)
        if cpf is not None:
            campos.append("cpf = ?")
            valores.append(cpf)
        if rg is not None:
            campos.append("rg = ?")
            valores.append(rg)
        if cep is not None:
            campos.append("cep = ?")
            valores.append(cep)
        if endereco is not None:
            campos.append("endereco = ?")
            valores.append(endereco)
        if numero is not None:
            campos.append("numero = ?")
            valores.append(numero)
        if complemento is not None:
            campos.append("complemento = ?")
            valores.append(complemento)
        if bairro is not None:
            campos.append("bairro = ?")
            valores.append(bairro)
        if cidade is not None:
            campos.append("cidade = ?")
            valores.append(cidade)
        if estado is not None:
            campos.append("estado = ?")
            valores.append(estado)
        if foto is not None:
            campos.append("foto = ?")
            valores.append(foto)

        if not campos:
            return {"sucesso": False, "mensagem": "Nenhum campo para atualizar"}

        # Adicionar campo de atualização
        campos.append("atualizado_em = ?")
        valores.append(datetime.now().isoformat())

        # Adicionar ID do usuário no final
        valores.append(usuario_id)

        query = f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?"
        cur.execute(query, valores)

        conn.commit()
        return {"sucesso": True, "mensagem": "Usuário atualizado com sucesso"}


def usuario_existe_por_email(email: str, username_excluir: str = "") -> bool:
    """Verifica se existe um usuário com o email especificado (excluindo o username informado)."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        if username_excluir:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE email = ? AND username != ?", (email, username_excluir))
        else:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE email = ?", (email,))
        
        count = cur.fetchone()[0]
        return count > 0


def listar_usuarios_com_biometria() -> List[str]:
    """Retorna lista de usuários que têm autenticação por digital habilitada."""
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM usuarios WHERE usa_biometria = 1 ORDER BY nome_completo")
        usuarios = [row[0] for row in cur.fetchall()]
        return usuarios