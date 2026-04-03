"""
clientes.py - Módulo para operações específicas com clientes.
Nota: Funções básicas de CRUD devem usar db.py
"""

from db import get_db_pool
from datetime import datetime
import requests
from typing import Optional, Dict, Any
import logging
import re
import sqlite3

from constants import CEP_API_URL, CEP_LENGTH, CEP_TIMEOUT, HTTP_OK

logger = logging.getLogger(__name__)


# =========================
# ✅ VALIDAÇÃO
# =========================
def validar_nome(nome: str) -> bool:
    """Valida nome do cliente."""
    return bool(nome and len(nome.strip()) >= 2)


def validar_telefone(telefone: str) -> bool:
    """Valida telefone (formato brasileiro)."""
    if not telefone:
        return True  # Opcional
    # Remove caracteres não numéricos
    numero = re.sub(r'\D', '', telefone)
    return len(numero) >= 10  # Mínimo 10 dígitos


def validar_cep(cep: str) -> bool:
    """Valida CEP brasileiro."""
    if not cep:
        return True  # Opcional
    return bool(re.match(r'^\d{5}-?\d{3}$', cep))


# =========================
# 📍 BUSCAR CEP AUTOMÁTICO (ViaCEP)
# =========================
def buscar_endereco_por_cep(cep: str) -> Optional[Dict[str, str]]:
    """
    Busca dados de endereço via ViaCEP.
    
    Args:
        cep: CEP com ou sem formatação
    
    Returns:
        Dict com endereço/bairro/cidade, ou None se não encontrado
    """
    try:
        # Limpar CEP
        cep_limpo = cep.replace("-", "").replace(".", "").strip()

        if len(cep_limpo) != CEP_LENGTH:
            logger.warning(f"CEP com comprimento inválido: {cep}")
            return None

        # Buscar no ViaCEP
        url = CEP_API_URL.format(cep=cep_limpo)
        resp = requests.get(url, timeout=CEP_TIMEOUT)

        if resp.status_code != HTTP_OK:
            logger.warning(f"ViaCEP retornou status {resp.status_code}")
            return None

        data = resp.json()

        # Verificar erro
        if "erro" in data:
            logger.info(f"CEP não encontrado no ViaCEP: {cep_limpo}")
            return None

        return {
            "endereco": data.get("logradouro", ""),
            "bairro": data.get("bairro", ""),
            "cidade": data.get("localidade", ""),
            "cep": data.get("cep", "")
        }

    except requests.RequestException as e:
        logger.error(f"Erro de requisição ao buscar CEP {cep}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro desconhecido ao buscar CEP: {e}")
        return None


# =========================
# ✏️ EDITAR CLIENTE
# =========================
def editar_cliente(
    cliente_id: int,
    nome: str,
    telefone: str = "",
    endereco: str = "",
    numero: str = "",
    bairro: str = "",
    cidade: str = "",
    cep: str = ""
) -> bool:
    """
    Edita os dados de um cliente.
    
    Args:
        cliente_id: ID do cliente
        nome: Nome do cliente
        telefone: Telefone
        endereco: Endereço (rua)
        numero: Número da casa
        bairro: Bairro
        cidade: Cidade
        cep: CEP
    
    Returns:
        bool: True se editado com sucesso
    """
    # Validação
    if not validar_nome(nome):
        logger.error("Nome inválido")
        return False
    if not validar_telefone(telefone):
        logger.error("Telefone inválido")
        return False
    if not validar_cep(cep):
        logger.error("CEP inválido")
        return False

    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()

        # Montar endereço completo
        endereco_completo = f"{endereco}, {numero}" if numero else endereco

        cur.execute("""
            UPDATE clientes
            SET nome=?, telefone=?, endereco=?, bairro=?, cidade=?, cep=?
            WHERE id=?
        """, (
            nome.strip(),
            telefone.strip(),
            endereco_completo,
            bairro.strip(),
            cidade.strip(),
            cep.strip(),
            cliente_id
        ))

        conn.commit()
        logger.info(f"Cliente {cliente_id} atualizado com sucesso")
        return True


# =========================
# 🔍 BUSCAR CLIENTE POR ID
# =========================
def get_cliente(cliente_id: int) -> Optional[Dict[str, Any]]:
    """
    Busca um cliente específico pelo ID.
    
    Args:
        cliente_id: ID do cliente
    
    Returns:
        Dict com dados do cliente, ou None se não encontrado
    """
    with get_db_pool().get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,))
        row = cur.fetchone()

        if row:
            return dict(row)
        else:
            logger.info(f"Cliente {cliente_id} não encontrado")
            return None