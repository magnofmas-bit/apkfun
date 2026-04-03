"""
produtos.py - Módulo para gerenciar produtos, preços variáveis e fotos.
Nota: Funções básicas de CRUD (criar, listar, buscar) devem usar db.py
"""

from db import get_db_pool, get_conn
from datetime import datetime
from typing import List, Dict, Optional
import logging
import sqlite3

logger = logging.getLogger(__name__)

# Limite máximo de fotos por produto
MAX_FOTOS_POR_PRODUTO = 3


# =========================
# ✅ VALIDAÇÃO
# =========================
def validar_produto(nome: str, preco: float, estoque: float) -> bool:
    """Valida dados do produto."""
    if not nome or len(nome.strip()) < 2:
        return False
    if preco < 0:
        return False
    if estoque < 0:
        return False
    return True


# =========================
# ✏️ EDITAR PRODUTO
# =========================
def editar_produto(
    produto_id: int,
    nome: str,
    preco: float,
    codigo_barras: str = "",
    unidade: str = "UN",
    estoque: float = 0
) -> bool:
    """
    Edita os dados de um produto.
    
    Args:
        produto_id: ID do produto
        nome: Novo nome
        preco: Novo preço
        codigo_barras: Novo código de barras
        unidade: Nova unidade de medida
        estoque: Quantidade em estoque
    
    Returns:
        bool: True se editado com sucesso
    """
    # Validação
    if not validar_produto(nome, preco, estoque):
        logger.error("Dados do produto inválidos")
        return False

    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            UPDATE produtos
            SET nome=?, preco=?, codigo_barras=?, unidade=?, estoque=?
            WHERE id=?
        """, (nome.strip(), preco, codigo_barras.strip(), unidade.strip(), estoque, produto_id))

        conn.commit()
        logger.info(f"Produto {produto_id} atualizado com sucesso")
        return True


# =========================
# 💰 VARIAÇÕES DE PREÇO
# =========================
def adicionar_preco_variavel(
    produto_id: int,
    quantidade_min: float,
    preco: float
) -> bool:
    """
    Adiciona uma faixa de preço variável para o produto.
    
    Args:
        produto_id: ID do produto
        quantidade_min: Quantidade mínima para este preço
        preco: Preço para esta quantidade
    
    Returns:
        bool: True se adicionado com sucesso
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO produto_precos (produto_id, quantidade_min, preco)
            VALUES (?, ?, ?)
        """, (produto_id, quantidade_min, preco))

        conn.commit()
        logger.info(f"Preço variável adicionado para produto {produto_id}")
        return True


def listar_precos_variaveis(produto_id: int) -> List[Dict]:
    """
    Retorna lista de preços variáveis para um produto.
    
    Args:
        produto_id: ID do produto
    
    Returns:
        List[Dict]: Lista de preços variáveis ordenados por quantidade
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT * FROM produto_precos
            WHERE produto_id=?
            ORDER BY quantidade_min ASC
        """, (produto_id,))

        dados = [dict(r) for r in cur.fetchall()]
        return dados
    
    except sqlite3.Error as e:
        logger.error(f"Erro ao listar preços variáveis: {e}")
        return []
    finally:
        conn.close()


# =========================
# 💰 PREÇO FINAL
# =========================
def calcular_preco(produto_id: int, quantidade: float) -> Optional[float]:
    """
    Calcula o preço final considerando preços variáveis.
    Se não encontrar regra de preço variável, retorna None apenas quando não houver faixas.
    Se houver faixas, retorna a faixa mais próxima (a menor quantidade mínima) quando a quantia for menor que a menor regra.
    
    Args:
        produto_id: ID do produto
        quantidade: Quantidade desejada
    
    Returns:
        float: Preço unitário conforme quantidade, ou None se não houver regra
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT quantidade_min, preco
            FROM produto_precos
            WHERE produto_id=?
            ORDER BY quantidade_min ASC
        """, (produto_id,))

        regras = cur.fetchall()

        if not regras:
            return None

        # Buscar a regra aplicável: a maior quantidade_min que seja <= quantidade
        aplicavel = None
        for r in reversed(regras):
            if quantidade >= float(r["quantidade_min"]):
                aplicavel = float(r["preco"])
                break

        if aplicavel is not None:
            return aplicavel

        # Se quantidade for menor que a menor regra, aplica o menor preço (primeira regra ordenada asc)
        primeiro_preco = float(regras[0]["preco"])
        return primeiro_preco
    
    except sqlite3.Error as e:
        logger.error(f"Erro ao calcular preço: {e}")
        return None
    finally:
        conn.close()


# =========================
# 📸 FOTOS DO PRODUTO
# =========================
def adicionar_foto(produto_id: int, caminho: str) -> bool:
    """
    Adiciona uma foto ao produto (máximo 3 fotos).
    
    Args:
        produto_id: ID do produto
        caminho: Caminho ou URL da foto
    
    Returns:
        bool: True se adicionado com sucesso, False se limite atingido
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        # Verificar limite de fotos
        cur.execute(
            "SELECT COUNT(*) as total FROM produto_fotos WHERE produto_id=?",
            (produto_id,)
        )
        row = cur.fetchone()
        total = row["total"] if row else 0

        if total >= MAX_FOTOS_POR_PRODUTO:
            logger.warning(f"Limite de fotos atingido para produto {produto_id}")
            return False

        # Adicionar foto
        cur.execute("""
            INSERT INTO produto_fotos (produto_id, caminho)
            VALUES (?, ?)
        """, (produto_id, caminho))

        conn.commit()
        logger.info(f"Foto adicionada ao produto {produto_id}")
        return True
    
    except sqlite3.Error as e:
        logger.error(f"Erro ao adicionar foto: {e}")
        return False
    finally:
        conn.close()


def listar_fotos(produto_id: int) -> List[str]:
    """
    Retorna lista de caminhos de fotos do produto.
    
    Args:
        produto_id: ID do produto
    
    Returns:
        List[str]: Lista de caminhos de fotos
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT caminho FROM produto_fotos WHERE produto_id=?
        """, (produto_id,))

        fotos = [r["caminho"] for r in cur.fetchall()]
        return fotos
    
    except sqlite3.Error as e:
        logger.error(f"Erro ao listar fotos: {e}")
        return []
    finally:
        conn.close()


# =========================
# 📦 ESTOQUE (PLACEHOLDER)
# =========================
def baixar_estoque(produto_id: int, quantidade: float) -> bool:
    """
    Baixa estoque do produto.
    
    Args:
        produto_id: ID do produto
        quantidade: Quantidade a baixar
    
    Returns:
        bool: True se bem-sucedido
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        # Verificar estoque atual
        cur.execute("SELECT estoque FROM produtos WHERE id = ?", (produto_id,))
        row = cur.fetchone()
        
        if not row:
            logger.error(f"Produto {produto_id} não encontrado")
            return False
        
        estoque_atual = float(row[0] or 0)
        
        # Se estoque é 0, significa que não há controle de estoque
        if estoque_atual <= 0:
            logger.info(f"Produto {produto_id} não tem controle de estoque ativo")
            return True
        
        # Verificar se há estoque suficiente
        if estoque_atual < quantidade:
            logger.error(f"Estoque insuficiente para produto {produto_id}: {estoque_atual} < {quantidade}")
            return False
        
        # Baixar estoque
        novo_estoque = estoque_atual - quantidade
        cur.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo_estoque, produto_id))
        
        conn.commit()
        logger.info(f"Estoque do produto {produto_id} baixado: {estoque_atual} -> {novo_estoque}")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Erro ao baixar estoque: {e}")
        return False
    finally:
        conn.close()