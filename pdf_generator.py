"""
pdf_generator.py - Módulo para geração de comprovantes em imagem PNG (cupom fiscal).
"""

import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


def gerar_comprovante(
    pedido_id: int,
    cliente: Dict[str, Any],
    itens: List[Dict[str, Any]],
    total: float,
    forma_pagamento: str
) -> Optional[str]:
    """
    Gera um comprovante de venda em imagem PNG (estilo cupom fiscal) com layout profissional.
    
    Args:
        pedido_id: ID do pedido
        cliente: Dicionário com dados do cliente
        itens: Lista de itens do pedido
        total: Valor total do pedido
        forma_pagamento: Forma de pagamento utilizada
    
    Returns:
        str: Caminho do arquivo PNG gerado, ou None se erro
    """

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pasta_png = os.path.join(base_dir, "dados", "pdfs")
        os.makedirs(pasta_png, exist_ok=True)

        nome_arquivo = f"pedido_{pedido_id}.png"
        caminho = os.path.join(pasta_png, nome_arquivo)

        # =========================
        # 🎨 DIMENSÕES E FONTES
        # =========================
        largura = 800
        altura_linha = 32
        padding = 30
        
        # Tentar usar fonte do sistema, senão usar padrão
        fonte_titulo = None
        fonte_normal = None
        fonte_pequena = None
        
        try:
            # Tentar carregar fontes do Windows
            fonte_titulo = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 24)
            fonte_normal = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 16)
            fonte_pequena = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 14)
        except:
            try:
                # Tentar fontes padrão do sistema
                fonte_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
                fonte_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                fonte_pequena = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                # Usar fonte padrão
                fonte_titulo = ImageFont.load_default()
                fonte_normal = ImageFont.load_default()
                fonte_pequena = ImageFont.load_default()

        # Calcular altura
        num_linhas = 20 + len(itens) * 2
        altura = num_linhas * altura_linha + padding * 2

        # Criar imagem branca
        img = Image.new('RGB', (largura, altura), color='white')
        draw = ImageDraw.Draw(img)

        # Função para desenhar texto
        def draw_text(y, text, align='left', font=None, espaco_extra=0):
            if font is None:
                font = fonte_normal
            
            if align == 'center':
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                x = (largura - text_width) // 2
            elif align == 'right':
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                x = largura - padding - text_width
            else:  # left
                x = padding
            
            draw.text((x, y), text, fill='black', font=font)
            return y + altura_linha + espaco_extra

        y = padding

        # =========================
        # CABEÇALHO
        # =========================
        y = draw_text(y, "╔" + "═" * 48 + "╗", 'center', font=fonte_normal)
        y = draw_text(y, "COMPROVANTE DE VENDA", 'center', font=fonte_titulo, espaco_extra=10)
        y = draw_text(y, "╚" + "═" * 48 + "╝", 'center', font=fonte_normal, espaco_extra=15)

        # =========================
        # PEDIDO E DATA
        # =========================
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        y = draw_text(y, f"Nº Pedido: {pedido_id}", font=fonte_normal)
        y = draw_text(y, f"Data: {data_atual}", font=fonte_normal, espaco_extra=15)

        # =========================
        # CLIENTE
        # =========================
        cliente_nome = cliente.get('nome', 'N/A') if cliente else 'N/A'
        cliente_telefone = cliente.get('telefone', '') if cliente else ''
        
        draw.line((padding, y, largura - padding, y), fill='black', width=1)
        y += altura_linha // 2
        
        y = draw_text(y, f"Cliente: {cliente_nome}", font=fonte_normal)
        if cliente_telefone:
            y = draw_text(y, f"Telefone: {cliente_telefone}", font=fonte_pequena)
        
        draw.line((padding, y + 5, largura - padding, y + 5), fill='black', width=1)
        y += altura_linha // 2 + 10

        # =========================
        # ITENS
        # =========================
        y = draw_text(y, "ITENS DO PEDIDO", 'center', font=fonte_titulo, espaco_extra=10)
        
        # Cabeçalho da tabela
        draw.line((padding, y, largura - padding, y), fill='black', width=2)
        y += 5
        y = draw_text(y, "Qtd  │  Descrição  │  Unit.  │  Subtotal", 'left', font=fonte_pequena, espaco_extra=8)
        draw.line((padding, y, largura - padding, y), fill='black', width=1)
        y += 5

        # Itens
        for item in itens:
            produto_nome = item.get('produto_nome', item.get('nome', 'N/A'))
            quantidade = item.get('quantidade', 1)
            preco_unit = item.get('preco_unitario', item.get('preco', 0))
            subtotal = quantidade * preco_unit

            # Formato quantidade sem decimais se for inteiro
            if isinstance(quantidade, float) and quantidade.is_integer():
                qtd_formatada = str(int(quantidade))
            else:
                qtd_formatada = str(quantidade)

            # Melhor distribuição
            linha_item = f"{qtd_formatada:>2} │ {produto_nome[:18]:<18} │ R$ {preco_unit:>6.2f} │ R$ {subtotal:>8.2f}"
            y = draw_text(y, linha_item, font=fonte_pequena)

        draw.line((padding, y, largura - padding, y), fill='black', width=2)
        y += altura_linha // 2

        # =========================
        # TOTAL
        # =========================
        y = draw_text(y, f"TOTAL: R$ {total:.2f}", 'center', font=fonte_titulo, espaco_extra=15)
        
        # =========================
        # PAGAMENTO
        # =========================
        y = draw_text(y, f"Forma de Pagamento: {forma_pagamento}", 'center', font=fonte_normal, espaco_extra=15)

        # =========================
        # RODAPÉ
        # =========================
        draw.line((padding, y, largura - padding, y), fill='black', width=1)
        y += altura_linha // 2
        y = draw_text(y, "Obrigado pela sua compra!", 'center', font=fonte_normal)
        y = draw_text(y, "Volte sempre!", 'center', font=fonte_pequena, espaco_extra=10)
        y = draw_text(y, "╔" + "═" * 48 + "╗", 'center', font=fonte_normal)

        # Salvar imagem
        img.save(caminho)
        logger.info(f"Cupom gerado: {caminho}")
        return caminho

    except Exception as e:
        logger.error(f"Erro ao gerar cupom PNG: {e}")
        return None

    except Exception as e:
        logger.error(f"Erro ao gerar cupom PNG: {e}")
        return None