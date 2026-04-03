#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db import list_pedidos

print("=== VERIFICANDO FORMATOS DE DATA DAS VENDAS ===")
pedidos = list_pedidos()

for i, pedido in enumerate(pedidos, 1):
    data_pedido = pedido.get('data_pedido', 'N/A')
    valor_total = pedido.get('valor_total', 0)
    cliente_nome = pedido.get('cliente_nome', 'N/A')

    print(f"Venda {i}:")
    print(f"  Data: '{data_pedido}' (tipo: {type(data_pedido)})")
    print(f"  Valor: R$ {valor_total}")
    print(f"  Cliente: {cliente_nome}")
    print()

print(f"Total de vendas encontradas: {len(pedidos)}")