"""
vendas.py - Módulo para gerenciar carrinho de compras e finalização de vendas.
"""

from produtos import calcular_preco, baixar_estoque
from db import salvar_pedido_local
from pdf_generator import gerar_comprovante
from datetime import datetime
import copy
from typing import List, Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class Venda:
    """Gerencia um pedido/carrinho de vendas."""

    def __init__(self):
        """Inicializa uma nova venda."""
        self.resetar_venda()

    def resetar_venda(self) -> None:
        """Reseta todos os dados da venda atual."""
        self.cliente: Optional[Dict[str, Any]] = None
        self.itens: List[Dict[str, Any]] = []
        self.total: float = 0.0
        self.forma_pagamento: str = "Dinheiro"

    def definir_cliente(self, cliente: Dict[str, Any]) -> None:
        self.cliente = cliente

    def definir_pagamento(self, forma: str) -> None:
        self.forma_pagamento = forma

    # =========================
    # 🔥 MELHORADO
    # =========================
    def adicionar_item(self, produto: Dict[str, Any], quantidade: float) -> bool:

        if not produto or "id" not in produto:
            logger.warning("Produto inválido ou sem ID")
            return False

        produto_id = produto.get("id")

        try:
            quantidade = float(quantidade)
        except (ValueError, TypeError):
            quantidade = 1.0

        if quantidade <= 0:
            quantidade = 1.0

        # Verificar estoque se controlado
        estoque = float(produto.get("estoque", 0))
        if estoque > 0:  # Só verifica se há controle de estoque
            # Calcular quantidade total que seria no carrinho
            quantidade_existente = 0
            for item in self.itens:
                if item["produto_id"] == produto_id:
                    quantidade_existente = item["quantidade"]
                    break
            
            quantidade_total = quantidade_existente + quantidade
            
            if quantidade_total > estoque:
                logger.warning(f"Estoque insuficiente: {estoque} disponível, solicitado {quantidade_total}")
                return False

        from produtos import listar_precos_variaveis

        # Se o produto já está no carrinho, soma quantidade para cálculo de preço variável
        quantidade_existente = 0
        item_existente = None
        for item in self.itens:
            if item["produto_id"] == produto_id:
                quantidade_existente = item["quantidade"]
                item_existente = item
                break

        quantidade_total = quantidade_existente + quantidade

        preco_unitario = calcular_preco(produto_id, quantidade_total)
        variacoes = listar_precos_variaveis(produto_id)

        if preco_unitario is None and variacoes:
            # Quando há regras de preço variável, usamos a primeira regra válida.
            preco_unitario = float(variacoes[-1].get("preco", 0)) if variacoes else produto.get("preco", 0)
            logger.info(f"Usando preço variável para produto {produto_id}: R$ {preco_unitario}")

        if preco_unitario is None:
            preco_unitario = produto.get("preco", 0)

        try:
            preco_unitario = float(preco_unitario)
        except Exception:
            preco_unitario = 0.0

        # 🔥 Se já existe, soma quantidade e recalcula com preço por variação
        if item_existente:
            item_existente["quantidade"] = quantidade_total
            item_existente["preco_unitario"] = preco_unitario
            item_existente["total"] = round(quantidade_total * preco_unitario, 2)
            self.calcular_total()
            logger.info(f"Quantidade atualizada: {item_existente['produto_nome']} (qtd: {quantidade_total}, preço: {preco_unitario:.2f})")
            return True

        # Novo item
        total_item = round(preco_unitario * quantidade, 2)

        item = {
            "produto_id": produto_id,
            "produto_nome": produto.get("nome", "Produto"),
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
            "total": total_item
        }

        self.itens.append(item)
        self.calcular_total()

        logger.info(f"Item adicionado: {produto.get('nome')} (qtd: {quantidade})")
        return True

    def remover_item(self, index: int) -> bool:
        if 0 <= index < len(self.itens):
            item_removido = self.itens.pop(index)
            logger.info(f"Item removido: {item_removido.get('produto_nome')}")
            self.calcular_total()
            return True

        logger.warning(f"Índice inválido para remoção: {index}")
        return False

    def alterar_quantidade(self, index: int, nova_quantidade: float) -> bool:
        """Altera a quantidade de um item no pedido."""
        if 0 <= index < len(self.itens):
            try:
                nova_quantidade = float(nova_quantidade)
                if nova_quantidade <= 0:
                    # Se quantidade <= 0, remove o item
                    return self.remover_item(index)
                
                item = self.itens[index]
                
                # Verificar estoque se controlado
                produto_id = item["produto_id"]
                # Buscar dados do produto para verificar estoque
                from db import get_conn
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT estoque FROM produtos WHERE id = ?", (produto_id,))
                row = cur.fetchone()
                conn.close()
                
                if row:
                    estoque = float(row[0] or 0)
                    if estoque > 0 and nova_quantidade > estoque:  # Só verifica se há controle de estoque
                        logger.warning(f"Estoque insuficiente: {estoque} disponível, solicitado {nova_quantidade}")
                        return False
                
                # Recalcular preço unitário com base em variações de quantidade
                from produtos import calcular_preco
                preco_unitario_atual = calcular_preco(produto_id, nova_quantidade)
                if preco_unitario_atual is None:
                    preco_unitario_atual = item.get("preco_unitario", 0)

                try:
                    preco_unitario_atual = float(preco_unitario_atual)
                except (ValueError, TypeError):
                    preco_unitario_atual = float(item.get("preco_unitario", 0))

                item["quantidade"] = nova_quantidade
                item["preco_unitario"] = preco_unitario_atual
                item["total"] = round(nova_quantidade * preco_unitario_atual, 2)
                self.calcular_total()
                logger.info(f"Quantidade alterada: {item['produto_nome']} para {nova_quantidade} com preço {preco_unitario_atual:.2f}")
                return True
            except (ValueError, TypeError) as e:
                logger.error(f"Erro ao alterar quantidade: {e}")
                return False
        
        logger.warning(f"Índice inválido para alteração: {index}")
        return False

    # =========================
    # 🔥 MELHORADO
    # =========================
    def calcular_total(self) -> None:
        try:
            total = 0.0
            for item in self.itens:
                total += float(item.get("total", 0))
            self.total = round(total, 2)
        except Exception as e:
            logger.error(f"Erro ao calcular total: {e}")
            self.total = 0.0

    def listar_itens(self) -> List[Dict[str, Any]]:
        return self.itens

    def finalizar_venda(self) -> Tuple[bool, Any]:
        try:
            if not self.cliente:
                return False, "Cliente não definido"

            if not self.itens:
                return False, "Nenhum item no pedido"

            cliente_id = None
            cliente_nome = None

            if isinstance(self.cliente, dict):
                cliente_id = self.cliente.get("id")
                cliente_nome = self.cliente.get("nome")

            # =========================
            # ESTOQUE
            # =========================
            for item in self.itens:
                try:
                    produto_id = item.get("produto_id")
                    quantidade = item.get("quantidade", 1)

                    if produto_id is None:
                        continue

                    ok = baixar_estoque(produto_id, quantidade)

                    if ok is False:
                        logger.warning(f"Falha ao baixar estoque para produto ID {produto_id}")

                except Exception as e:
                    logger.error(f"Erro ao processar estoque: {e}")

            itens_copia = copy.deepcopy(self.itens)
            total_copia = self.total
            forma_pagamento = self.forma_pagamento

            payload = {
                "pedido_client_id": f"venda-{int(datetime.now().timestamp())}",
                "cliente_id": cliente_id,
                "cliente_nome": cliente_nome,
                "forma_pagamento": forma_pagamento,
                "itens": itens_copia,
                "valor_total": total_copia
            }

            try:
                pedido_id = salvar_pedido_local(payload, itens_copia)
            except Exception as e:
                logger.error(f"Erro ao salvar pedido: {e}")
                return False, f"Erro ao salvar pedido: {e}"

            # Gerar comprovante PDF
            pdf_path = gerar_comprovante(pedido_id, self.cliente, itens_copia, total_copia, forma_pagamento)
            if pdf_path:
                logger.info(f"Comprovante gerado: {pdf_path}")
            else:
                logger.warning("Falha ao gerar comprovante PDF")

            self.resetar_venda()

            logger.info(f"Venda finalizada com sucesso. Pedido ID: {pedido_id}")

            return True, {
                "pedido_id": pedido_id,
                "cliente": cliente_nome,
                "itens": itens_copia,
                "total": total_copia,
                "pagamento": forma_pagamento,
                "pdf_path": pdf_path
            }

        except Exception as e:
            logger.error(f"Erro ao finalizar venda: {e}")
            return False, f"Erro venda: {e}"