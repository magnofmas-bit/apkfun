"""Módulo principal da aplicação Kivy - Versão Otimizada."""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty, StringProperty, DictProperty, NumericProperty
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView

import requests, logging, os, sys
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from vendas import Venda
from db import init_db, list_clientes, add_cliente, list_produtos, add_produto, list_pedidos, get_itens_pedido, update_pedido_status, add_usuario, verificar_login, usuario_existe, verificar_biometria_habilitada, listar_usuarios_com_biometria, atualizar_biometria_usuario, atualizar_usuario, get_conn
from clientes import editar_cliente as editar_cliente_db
from constants import *

logger = logging.getLogger(__name__)

class RootWidget(BoxLayout):
    """Widget raiz da aplicação."""
    clientes = ListProperty([])
    produtos = ListProperty([])
    clientes_spinner_values = ListProperty([])
    produtos_spinner_values = ListProperty([])
    status_log = StringProperty("Iniciado")
    pedidos = ListProperty([])
    vendedor = DictProperty({})
    total_vendas = NumericProperty(0.0)
    comissao = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.venda = Venda()
        self.cliente_selecionado = None
        self.produto_selecionado = None
        self.usuario_logado = None
        self.cliente_em_edicao_id = None
        self.produto_em_edicao_id = None
        self.calendario_mes = datetime.now().month
        self.calendario_ano = datetime.now().year

    def on_kv_post(self, *args):
        """Inicializa após carregar arquivo KV."""
        self._mostrar_telas_login()
        try:
            self.ids.tab_panel.default_tab = self.ids.login_tab
            self.ids.tab_panel.switch_to(self.ids.login_tab)
        except: pass
        try:
            self.reload_data()
            self.carregar_pedidos()
            logger.info("Dados iniciais carregados")
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")

    # ==================== DADOS ====================
    def reload_data(self): 
        try:
            self.clientes = list_clientes()
            self.produtos = list_produtos()
            self.clientes_spinner_values = [PLACEHOLDER_CHOOSE] + [f"{c['id']} - {c['nome']}" for c in self.clientes]
            self.produtos_spinner_values = [PLACEHOLDER_CHOOSE] + [f"{p['id']} - {p['nome']}" for p in self.produtos]
            try: self.atualizar_lista_produtos()
            except: pass
        except Exception as e:
            logger.error(f"Erro recarregar: {e}")
            self.log(LOG_RELOAD_ERROR.format(e))

    def carregar_pedidos(self):
        try:
            self.pedidos = list_pedidos()
            self._atualizar_lista_pedidos()
            self._atualizar_lista_vendas_comissao()
            self.atualizar_comissao_vendedor()
        except Exception as e:
            logger.error(f"Erro pedidos: {e}")

    # ==================== HELPER METHODS ====================
    def log(self, msg: str) -> None:
        self.status_log = msg
        try: self.ids.status_label.text = msg
        except: pass

    def _get_texto(self, widget_id: str) -> str:
        try: return self.ids.get(widget_id).text.strip() if hasattr(self.ids, widget_id) else ""
        except: return ""

    def _criar_label_tabela(self, text: str, size_hint_x: float, negrito=False, cor=(0,0,0,1), font_size="11sp") -> Label:
        return Label(text=text, size_hint_x=size_hint_x, color=cor, font_size=font_size, bold=negrito, halign="center")

    def _criar_botao(self, texto: str, size_hint_x=0.15, altura=40, cor=(0.01, 0.45, 0.89, 1), callback=None):
        btn = Button(text=texto, size_hint_x=size_hint_x, size_hint_y=None, height=altura, background_color=cor, color=(1,1,1,1), font_size="10sp")
        if callback: btn.bind(on_release=callback)
        return btn

    def _abrir_popup(self, titulo, conteudo, size_hint=(0.8, 0.6)):
        popup = Popup(title=titulo, content=conteudo, size_hint=size_hint)
        popup.open()
        return popup

    def _converter_data(self, data_str: str) -> Optional[datetime]:
        """Converte múltiplos formatos de data."""
        if not data_str: return None
        data_str = data_str.strip()
        for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
            try:
                dt = datetime.strptime(data_str, fmt)
                return dt.replace(hour=0, minute=0, second=0, microsecond=0)
            except: continue
        return None

    def _controlar_abas(self, habilitar_login=True):
        """Controla visibilidade de abas."""
        for aba_id in ["login_tab", "cadastro_tab"]:
            self.ids[aba_id].disabled = not habilitar_login
        for aba_id in ["tab_clientes", "tab_produtos", "tab_venda", "comissao_tab", "tab_pedidos", "tab_inventario"]:
            try: self.ids[aba_id].disabled = habilitar_login
            except: pass

    # ==================== PEDIDOS ====================
    def _atualizar_lista_pedidos(self):
        try:
            box = self.ids.pedidos_list_box
            box.clear_widgets()
            pedidos_filtrados = self._get_pedidos_filtrados()
            
            if not pedidos_filtrados:
                box.add_widget(Label(text="Nenhum pedido encontrado", size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            # Cabeçalho
            header_layout = BoxLayout(size_hint_y=None, height="40dp", spacing=1, padding=[5, 5, 5, 5])
            for header, width in zip(["ID", "Cliente", "Data", "Produtos", "Total", "Ações"], [0.1, 0.25, 0.15, 0.3, 0.12, 0.08]):
                header_layout.add_widget(Label(text=f"[b]{header}[/b]", markup=True, size_hint_x=width, font_size="12sp", bold=True, color=(0.2, 0.2, 0.2, 1), halign="center"))
            box.add_widget(header_layout)

            # Linhas de dados
            for pedido in pedidos_filtrados:
                row = BoxLayout(size_hint_y=None, height="35dp", spacing=1, padding=[5, 2, 5, 2])
                cor_row = (0.98, 0.98, 0.98, 1) if len(box.children) % 2 == 0 else (1, 1, 1, 1)
                row.canvas.before.clear()
                with row.canvas.before:
                    Color(*cor_row)
                    Rectangle(pos=row.pos, size=row.size)
                row.bind(pos=lambda i, v: setattr(row.canvas.before.children[-1], 'pos', v) if row.canvas.before.children else None,
                        size=lambda i, v: setattr(row.canvas.before.children[-1], 'size', v) if row.canvas.before.children else None)

                row.add_widget(Label(text=str(pedido['id']), size_hint_x=0.1, font_size="11sp", color=(0.3,0.3,0.3,1), halign="center"))
                row.add_widget(Label(text=pedido.get('cliente_nome', 'N/A'), size_hint_x=0.25, font_size="11sp", color=(0.2,0.2,0.2,1)))
                
                # Data
                data_formatada = "N/A"
                try:
                    data_obj = datetime.fromisoformat(pedido.get('data_pedido', '').replace('Z', '+00:00'))
                    data_formatada = data_obj.strftime('%d/%m/%Y')
                except:
                    try:
                        data_str = pedido.get('data_pedido', '')
                        data_formatada = data_str[:10] if data_str else "N/A"
                    except: pass
                row.add_widget(Label(text=data_formatada, size_hint_x=0.15, font_size="11sp", color=(0.3,0.3,0.3,1), halign="center"))

                # Produtos resumo
                itens = get_itens_pedido(pedido['id'])
                produtos_texto = ", ".join([f"{item.get('produto_nome', 'N/A')[:20]}({item.get('quantidade', 0):.0f}x)" for item in itens[:3]])
                if len(itens) > 3: produtos_texto += "..."
                row.add_widget(Label(text=produtos_texto, size_hint_x=0.3, font_size="10sp", color=(0.3,0.3,0.3,1)))

                valor = pedido.get('valor_total', pedido.get('total', 0))
                row.add_widget(Label(text=f"R$ {valor:.2f}", size_hint_x=0.12, font_size="11sp", bold=True, color=(0.1,0.6,0.1,1), halign="right"))

                # Botões
                acoes = BoxLayout(size_hint_x=0.08, orientation='horizontal', spacing=1)
                btn_editar = self._criar_botao("✏️", 0.5, cor=(0.01, 0.45, 0.89, 1), callback=lambda b, pid=pedido['id']: self._abrir_edicao_venda(pid))
                btn_compartilhar = self._criar_botao("📤", 0.5, cor=(0.1, 0.8, 0.1, 1), callback=lambda b, pid=pedido['id']: self.compartilhar_comprovante(pid))
                acoes.add_widget(btn_editar)
                acoes.add_widget(btn_compartilhar)
                row.add_widget(acoes)

                box.add_widget(row)
        except Exception as e:
            logger.error(f"Erro atualizar pedidos: {e}")

    def _get_pedidos_filtrados(self) -> List[Dict]:
        try:
            filtro = self._get_texto("pedidos_busca_cliente").lower() if hasattr(self.ids, 'pedidos_busca_cliente') else ""
            return [p for p in self.pedidos if not filtro or filtro in p.get('cliente_nome', '').lower()] if filtro else self.pedidos
        except: return self.pedidos

    def filtrar_pedidos_por_cliente(self): self._atualizar_lista_pedidos()
    def limpar_filtro_pedidos(self):
        try: self.ids.pedidos_busca_cliente.text = ""
        except: pass
        self._atualizar_lista_pedidos()

    def _abrir_edicao_venda(self, pedido_id: int):
        try:
            pedido = next((p for p in self.pedidos if p['id'] == pedido_id), None)
            if not pedido: return
            
            cliente = next((c for c in self.clientes if c['id'] == pedido['cliente_id']), None)
            if cliente:
                self.cliente_selecionado = cliente
                self.ids.clientes_search.text = cliente['nome']
            
            self.venda = Venda()
            for item in get_itens_pedido(pedido_id):
                produto = next((p for p in self.produtos if p['id'] == item['produto_id']), None)
                if produto: self.venda.adicionar_item(produto, item['quantidade'])
            
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            self.ids.pagamento_spinner.text = pedido.get('forma_pagamento', 'Dinheiro')
            self.ids.tab_panel.switch_to(self.ids.tab_venda)
            self.log(f"Pedido #{pedido_id} carregado para edição")
        except Exception as e:
            logger.error(f"Erro editar venda: {e}")
            self.log(f"Erro ao editar pedido: {e}")

    def _mostrar_popup_compartilhar(self, pedido_id: int):
        try:
            box = BoxLayout(orientation='vertical', spacing=10, padding=20)
            box.add_widget(Label(text=f"[b]Pedido {pedido_id} finalizado!\\n\\nDeseja compartilhar o comprovante?[/b]", markup=True, size_hint_y=0.6, text_size=(300, None), halign='center'))
            
            btn_layout = BoxLayout(size_hint_y=0.4, spacing=10)
            popup = Popup(title="Compartilhar Comprovante", content=box, size_hint=(0.8, 0.4))
            
            btn_sim = Button(text="Sim, Compartilhar", background_color=(0.1, 0.8, 0.1, 1))
            btn_sim.bind(on_release=lambda x: [self.compartilhar_comprovante(pedido_id), popup.dismiss()])
            btn_nao = Button(text="Não", background_color=(0.8, 0.1, 0.1, 1))
            btn_nao.bind(on_release=lambda x: popup.dismiss())
            
            btn_layout.add_widget(btn_sim)
            btn_layout.add_widget(btn_nao)
            box.add_widget(btn_layout)
            popup.open()
        except Exception as e:
            logger.error(f"Erro popup compartilhar: {e}")

    def compartilhar_comprovante(self, pedido_id: Optional[int] = None):
        try:
            if pedido_id is None:
                pedido_id = getattr(self, 'last_pedido_id', None)
                if not pedido_id: self.log("Nenhum pedido selecionado"); return
            
            pedido = next((p for p in self.pedidos if p['id'] == pedido_id), None)
            if not pedido: self.log(f"Pedido {pedido_id} não encontrado"); return
            
            itens = get_itens_pedido(pedido_id)
            try:
                from pdf_generator import gerar_comprovante
                png_path = gerar_comprovante(pedido_id, {'id': pedido.get('cliente_id'), 'nome': pedido.get('cliente_nome'), 'telefone': pedido.get('cliente_telefone', '')}, itens, pedido.get('valor_total', 0), pedido.get('forma_pagamento', 'Não informado'))
                
                if png_path and os.path.exists(png_path):
                    if platform == 'android':
                        try:
                            from jnius import autoclass
                            Intent, Uri = autoclass('android.content.Intent'), autoclass('android.net.Uri')
                            PythonActivity = autoclass('org.kivy.android.PythonActivity')
                            intent = Intent()
                            intent.setAction(Intent.ACTION_VIEW)
                            intent.setDataAndType(Uri.parse(f"file://{png_path}"), "image/png")
                            PythonActivity.mActivity.startActivity(intent)
                        except: self.log(f"Comprovante gerado em: {png_path}")
                    else:
                        try: os.startfile(png_path)
                        except:
                            import subprocess
                            subprocess.Popen(['xdg-open' if sys.platform != 'darwin' else 'open', png_path])
                    self.log(f"Comprovante do pedido {pedido_id} aberto.")
            except ImportError:
                self.log("Módulo pdf_generator não disponível")
        except Exception as e:
            logger.error(f"Erro compartilhar: {e}")
            self.log(f"Erro ao abrir comprovante: {e}")

    # ==================== CLIENTES ====================
    def add_cliente_ui(self):
        try:
            nome = self._get_texto("cliente_nome_input")
            if not nome: self.log(ERROR_CLIENT_REQUIRED); return

            cliente_data = {
                "nome": nome,
                "telefone": self._get_texto("cliente_telefone_input"),
                "cep": self._get_texto("cliente_cep_input"),
                "endereco": self._get_texto("cliente_endereco_input"),
                "numero": self._get_texto("cliente_numero_input"),
                "bairro": self._get_texto("cliente_bairro_input"),
                "cidade": self._get_texto("cliente_cidade_input")
            }

            if hasattr(self, 'cliente_em_edicao_id') and self.cliente_em_edicao_id:
                sucesso = editar_cliente_db(self.cliente_em_edicao_id, cliente_data['nome'], cliente_data['telefone'], cliente_data['endereco'], cliente_data['numero'], cliente_data['bairro'], cliente_data['cidade'], cliente_data['cep'])
                self.log(f"✅ Cliente '{nome}' {'atualizado' if sucesso else 'não atualizado'}!")
                self.cliente_em_edicao_id = None
                if hasattr(self.ids, 'cliente_salvar_button'): self.ids.cliente_salvar_button.text = "Salvar Cliente"
            else:
                add_cliente(cliente_data)
                self.log(SUCCESS_CLIENTE_ADDED.format(nome))

            for campo in ["cliente_nome_input", "cliente_telefone_input", "cliente_cep_input", "cliente_endereco_input", "cliente_numero_input", "cliente_bairro_input", "cliente_cidade_input"]:
                try: self.ids[campo].text = ""
                except: pass
            self.reload_data()
        except Exception as e:
            logger.error(f"Erro add cliente: {e}")
            self.log(LOG_CLIENTE_ERROR.format(e))

    def editar_cliente_ui(self, cliente_id: int):
        try:
            cliente = next((c for c in self.clientes if c.get('id') == cliente_id), None)
            if not cliente: self.log(f"Cliente {cliente_id} não encontrado"); return

            self.cliente_em_edicao_id = cliente_id
            for campo, chave in [("cliente_nome_input", 'nome'), ("cliente_telefone_input", 'telefone'), ("cliente_cep_input", 'cep'), ("cliente_endereco_input", 'endereco'), ("cliente_numero_input", 'numero'), ("cliente_bairro_input", 'bairro'), ("cliente_cidade_input", 'cidade')]:
                try: self.ids[campo].text = cliente.get(chave, '')
                except: pass

            try: self.ids.cliente_salvar_button.text = "Atualizar Cliente"
            except: pass
            self.log(f"Editando cliente: {cliente.get('nome')}")
        except Exception as e:
            logger.error(f"Erro editar cliente: {e}")

    def buscar_cep(self):
        try:
            cep = self._get_texto("cliente_cep_input").replace("-", "")
            if not cep.isdigit() or len(cep) != CEP_LENGTH: self.log(ERROR_CEP_INVALID); return

            response = requests.get(CEP_API_URL.format(cep=cep), timeout=CEP_TIMEOUT)
            data = response.json()
            if data.get("erro"): self.log(ERROR_CEP_NOT_FOUND); return

            self.ids.cliente_endereco_input.text = data.get("logradouro", "")
            self.ids.cliente_bairro_input.text = data.get("bairro", "")
            self.ids.cliente_cidade_input.text = data.get("localidade", "")
            self.log(SUCCESS_ENDEREÇO_FILLED)
        except Exception as e:
            logger.error(f"Erro CEP: {e}")
            self.log(LOG_CEP_ERROR.format(e))

    def _exibir_clientes(self, lista_clientes: List[Dict]):
        try:
            if not hasattr(self.ids, 'clientes_list_box'): return
            box = self.ids.clientes_list_box
            box.clear_widgets()

            if not lista_clientes:
                box.add_widget(Label(text="Nenhum cliente encontrado", size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            for cliente in lista_clientes:
                container = BoxLayout(size_hint_y=None, height=50, padding=5, spacing=8, orientation="horizontal")
                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)
                    rect = Rectangle(size=container.size, pos=container.pos)
                container.bind(pos=lambda i, v: setattr(rect, 'pos', v), size=lambda i, v: setattr(rect, 'size', v))

                nome_btn = Button(text=str(cliente.get('nome', 'N/A')), size_hint_x=0.25, font_size='12sp', background_color=(0.2, 0.45, 0.8, 0.9), color=(1, 1, 1, 1))
                nome_btn.bind(on_release=lambda b, cid=cliente.get('id'): self.editar_cliente_ui(cid))

                endereco_parts = [cliente.get('endereco', ''), f"nº {cliente.get('numero', '')}" if cliente.get('numero', '') else "", cliente.get('bairro', ''), cliente.get('cidade', '')]
                endereco_text = ', '.join([p for p in endereco_parts if p])
                info_text = f"ID:{cliente.get('id')} | Tel:{cliente.get('telefone', 'N/A')} | {endereco_text or 'Endereço não informado'}"

                info_label = Label(text=info_text, size_hint_x=0.75, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='left')
                info_label.bind(size=lambda l, v: setattr(l, 'text_size', (v[0], v[1])))

                container.add_widget(nome_btn)
                container.add_widget(info_label)
                box.add_widget(container)
        except Exception as e:
            logger.error(f"Erro exibir clientes: {e}")

    def filtrar_clientes(self, termo: str):
        try:
            termo = (termo or "").strip().lower()
            if not termo:
                self._exibir_clientes(self.clientes)
                return
            resultados = [c for c in self.clientes if any(termo in str(c.get(k, '')).lower() for k in ['nome', 'endereco', 'numero', 'bairro', 'cidade', 'telefone'])]
            self._exibir_clientes(resultados)
        except Exception as e:
            logger.error(f"Erro filtrar clientes: {e}")

    def atualizar_lista_clientes(self):
        try:
            if hasattr(self.ids, 'clientes_list_box'): self._exibir_clientes(self.clientes)
        except Exception as e:
            logger.error(f"Erro atualizar clientes: {e}")

    # ==================== PRODUTOS ====================
    def add_produto_ui(self):
        try:
            nome = self._get_texto("produto_nome_input")
            if not nome: self.log("ERRO: Nome do produto é obrigatório!"); return

            self.calcular_preco_por_variacao()
            preco_str = self._get_texto("produto_preco_input").replace(",", ".")
            if not preco_str: self.log("ERRO: Preço do produto é obrigatório!"); return

            try:
                preco = float(preco_str)
                if preco <= 0: self.log("ERRO: Preço deve ser maior que zero!"); return
            except ValueError:
                self.log("ERRO: Preço inválido!"); return

            estoque = float(self._get_texto("produto_estoque_input").replace(",", ".")) if self._get_texto("produto_estoque_input") else 0.0

            produto_data = {
                "nome": nome,
                "preco": preco,
                "codigo_barras": self._get_texto("produto_codigo_input"),
                "unidade": "UN",
                "estoque": estoque
            }

            if hasattr(self, 'produto_em_edicao_id') and self.produto_em_edicao_id:
                from produtos import editar_produto
                sucesso = editar_produto(self.produto_em_edicao_id, nome, preco, produto_data["codigo_barras"], "UN", estoque)
                self.log(f"{'✅ Produto' if sucesso else '❌ Erro ao'} atualizar '{nome}'!")
                if sucesso:
                    conn = get_conn()
                    conn.cursor().execute("DELETE FROM produto_precos WHERE produto_id = ?", (self.produto_em_edicao_id,))
                    conn.commit()
                    conn.close()
                produto_id = self.produto_em_edicao_id
                delattr(self, 'produto_em_edicao_id')
            else:
                produto_id = add_produto(produto_data)
                self.log(SUCCESS_PRODUTO_ADDED.format(nome))

            # Salvar variações
            from produtos import adicionar_preco_variavel
            variacoes_salvas = 0
            for i in range(1, 6):
                qtd_str = self._get_texto(f"produto_qtd{i}_input").replace(",", ".")
                preco_var_str = self._get_texto(f"produto_preco{i}_input").replace(",", ".")
                if qtd_str and preco_var_str:
                    try:
                        qtd_min, preco_var = float(qtd_str), float(preco_var_str)
                        if qtd_min > 0 and preco_var > 0:
                            if adicionar_preco_variavel(produto_id, qtd_min, preco_var): variacoes_salvas += 1
                    except ValueError: pass

            if variacoes_salvas > 0: self.log(f"✅ {variacoes_salvas} variações de preço salvas!")

            # Limpar campos
            for campo in ["produto_nome_input", "produto_preco_input", "produto_codigo_input", "produto_estoque_input", "produto_busca_input"]:
                try: self.ids[campo].text = ""
                except: pass
            for i in range(1, 6):
                try:
                    self.ids[f"produto_qtd{i}_input"].text = ""
                    self.ids[f"produto_preco{i}_input"].text = ""
                except: pass

            self.ids.produto_preco_input.disabled = False
            self.ids.produto_preco_input.foreground_color = (0, 0, 0, 1)
            self.ids.btn_salvar_produto.text = "Salvar Produto"
            self.toggle_variacoes()
            self.reload_data()
            self.atualizar_lista_produtos()
        except Exception as e:
            logger.error(f"Erro add produto: {e}")
            self.log(LOG_PRODUTO_ERROR.format(e))

    def carregar_produtoedicao(self, produto_id: int):
        try:
            produto = next((p for p in self.produtos if p['id'] == produto_id), None)
            if not produto: self.log("Produto não encontrado!"); return

            self.ids.produto_nome_input.text = produto.get('nome', '')
            self.ids.produto_preco_input.text = str(produto.get('preco', ''))
            self.ids.produto_codigo_input.text = produto.get('codigo_barras', '')
            self.ids.produto_estoque_input.text = str(produto.get('estoque', ''))

            from produtos import listar_precos_variaveis
            variacoes = listar_precos_variaveis(produto_id)
            for i in range(1, 6):
                if i <= len(variacoes):
                    var = variacoes[i-1]
                    self.ids[f'produto_qtd{i}_input'].text = str(int(var.get('quantidade_min', '')))
                    self.ids[f'produto_preco{i}_input'].text = str(var.get('preco', ''))
                else:
                    self.ids[f'produto_qtd{i}_input'].text = ""
                    self.ids[f'produto_preco{i}_input'].text = ""

            self.calcular_preco_por_variacao()
            self.produto_em_edicao_id = produto_id
            self.ids.btn_salvar_produto.text = "Atualizar Produto"
            self.log(f"✏️ Editando: {produto.get('nome')}")
        except Exception as e:
            logger.error(f"Erro carregar produto: {e}")
            self.log(f"Erro ao carregar produto: {e}")

    def calcular_preco_por_variacao(self):
        try:
            preco_input = self.ids.produto_preco_input
            variacoes = []
            for i in range(1, 6):
                qtd_text = self.ids[f"produto_qtd{i}_input"].text.strip()
                preco_text = self.ids[f"produto_preco{i}_input"].text.strip()
                if qtd_text and preco_text:
                    try:
                        qtd_val, preco_val = float(qtd_text.replace(",", ".")), float(preco_text.replace(",", "."))
                        if qtd_val > 0 and preco_val > 0: variacoes.append((qtd_val, preco_val))
                    except ValueError: pass

            if variacoes:
                variacoes.sort(key=lambda x: x[0])
                preco_padrao = variacoes[0][1]
                if not preco_input.text.strip() or float(preco_input.text.replace(",", ".")) == 0:
                    preco_input.text = f"{preco_padrao:.2f}"
                preco_input.disabled = True
                preco_input.foreground_color = (0.5, 0.5, 0.5, 1)
                self.log("🧩 Preço base desativado por variações")
            else:
                preco_input.disabled = False
                preco_input.foreground_color = (0, 0, 0, 1)
        except Exception as e:
            logger.warning(f"Erro calcular preço: {e}")

    def toggle_variacoes(self): pass

    def _exibir_produtos(self, lista: List[Dict]):
        try:
            if not hasattr(self.ids, 'produtos_list_box'): return
            box = self.ids.produtos_list_box
            box.clear_widgets()

            if not lista:
                box.add_widget(Label(text="Nenhum produto encontrado", size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            for produto in lista:
                container = BoxLayout(size_hint_y=None, height=55, padding=5, spacing=5, orientation="vertical")
                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)
                    rect = Rectangle(size=container.size, pos=container.pos)
                container.bind(pos=lambda i, v: setattr(rect, 'pos', v), size=lambda i, v: setattr(rect, 'size', v))

                estoque = float(produto.get('estoque', 0))
                from produtos import listar_precos_variaveis
                variacoes = listar_precos_variaveis(produto.get('id', 0))
                tem_variacoes = len(variacoes) > 0

                altura_container = 75 if tem_variacoes else 55
                container.height = altura_container

                linha1 = BoxLayout(size_hint_y=0.4, spacing=5)
                linha1.add_widget(Label(text=f"ID: {produto.get('id')}", size_hint_x=0.15, font_size="11sp", bold=True, color=(0.1, 0.1, 0.1, 1)))
                linha1.add_widget(Label(text=f"{produto.get('nome', 'N/A')}", size_hint_x=0.35, font_size="12sp", bold=True, color=(0.8, 0.1, 0.1, 1) if estoque <= 0 else (0.1, 0.1, 0.1, 1)))
                linha1.add_widget(Label(text=f"R$ {float(produto.get('preco', 0)):.2f}", size_hint_x=0.2, font_size="12sp", bold=True, color=(0.1, 0.6, 0.1, 1)))
                linha1.add_widget(Label(text=f"Est: {estoque:.1f}" if estoque > 0 else "Est: —", size_hint_x=0.15, font_size="11sp", bold=True, color=(0.8, 0.1, 0.1, 1) if estoque <= 0 else (0.4, 0.4, 0.4, 1)))

                btn_editar = self._criar_botao("✏️ Editar", 0.15, callback=lambda b, pid=produto.get('id'): self.carregar_produtoedicao(pid))
                linha1.add_widget(btn_editar)

                if tem_variacoes:
                    variacoes_text = "Variações: " + " | ".join([f"{int(var.get('quantidade_min', 0))}+ R$ {var.get('preco', 0):.2f}" for var in variacoes[:3]])
                    if len(variacoes) > 3: variacoes_text += "..."
                    linha2 = Label(text=variacoes_text, size_hint_y=0.3, font_size="9sp", color=(0.2, 0.5, 0.8, 1), halign="left")
                else:
                    codigo = produto.get('codigo_barras', '') or "—"
                    linha2 = Label(text=f"Código: {codigo}", size_hint_y=0.3, font_size="10sp", color=(0.4, 0.4, 0.4, 1), halign="left")

                container.add_widget(linha1)
                container.add_widget(linha2)
                box.add_widget(container)
        except Exception as e:
            logger.error(f"Erro exibir produtos: {e}")

    def filtrar_produtos(self, texto: str):
        try:
            texto = texto.strip().lower()
            if not texto:
                self.atualizar_lista_produtos()
                return
            produtos_filtrados = [p for p in self.produtos if texto in str(p.get('nome', '')).lower() or texto in str(p.get('id', '')).lower()]
            self._exibir_produtos(produtos_filtrados)
        except Exception as e:
            logger.error(f"Erro filtrar produtos: {e}")

    def atualizar_lista_produtos(self):
        try:
            if hasattr(self.ids, 'produtos_list_box'): self._exibir_produtos(self.produtos)
        except Exception as e:
            logger.error(f"Erro atualizar produtos: {e}")

    # ==================== VENDEDOR ====================
    def add_vendedor_ui(self):
        try:
            if self.vendedor.get('nome'): self.log("Vendedor já cadastrado."); return

            nome = self._get_texto('vendedor_nome_input')
            cpf = self._get_texto('vendedor_cpf_input')
            if not nome or not cpf: self.log(('Nome do vendedor é obrigatório.' if not nome else 'CPF do vendedor é obrigatório.')); return

            self.vendedor = {'nome': nome, 'cpf': cpf, 'rg': self._get_texto('vendedor_rg_input'), 'endereco': self._get_texto('vendedor_endereco_input'), 'bairro': self._get_texto('vendedor_bairro_input'), 'cidade': self._get_texto('vendedor_cidade_input')}

            for field in ['vendedor_nome_input', 'vendedor_cpf_input', 'vendedor_rg_input', 'vendedor_endereco_input', 'vendedor_bairro_input', 'vendedor_cidade_input']:
                try: self.ids[field].disabled = True
                except: pass

            self.log(f"Vendedor cadastrado: {nome} ({cpf})")
            self.atualizar_comissao_vendedor()
        except Exception as e:
            logger.error(f"Erro vendedor: {e}")
            self.log(LOG_PRODUTO_ERROR.format(e))

    def atualizar_comissao_vendedor(self):
        try:
            total = sum(pedido.get('valor_total', 0) for pedido in self.pedidos)
            self.total_vendas = total
            commission = total * 0.05 if total <= 50000 else 50000 * 0.05 + (total - 50000) * 0.06
            self.comissao = commission

            try: self.ids.total_vendas_label.text = f"R$ {self.total_vendas:.2f}"
            except: pass
            try: self.ids.comissao_label.text = f"R$ {self.comissao:.2f}"
            except: pass
            try: self.ids.vendedor_label.text = f"Vendedor: {self.vendedor.get('nome', '-')}"
            except: pass
        except Exception as e:
            logger.error(f"Erro comissão: {e}")

    def handle_login(self):
        if not self.vendedor.get('nome'):
            self.log("Vendedor não cadastrado. Acesse a aba Login para cadastrar.")
            try: self.ids.tab_panel.switch_to(self.ids.login_tab)
            except: pass
            return
        self.log(f"Login efetuado: {self.vendedor.get('nome')}")
        self.atualizar_comissao_vendedor()
        self._atualizar_lista_vendas_comissao()
        try: self.ids.tab_panel.switch_to(self.ids.comissao_tab)
        except: pass

    # ==================== COMISSÃO ====================
    def carregar_datas_comissao(self):
        try:
            if not self.pedidos: return
            datas_validas = []
            for pedido in self.pedidos:
                data_str = pedido.get('data_pedido', '')
                if data_str:
                    try:
                        datetime.strptime(data_str.strip(), "%d/%m/%Y")
                        datas_validas.append(data_str.strip())
                    except ValueError: pass

            if not datas_validas: return
            datas_ordenadas = sorted(datas_validas, key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
            
            try:
                if not self.ids.filtro_data_inicio_input.text.strip(): self.ids.filtro_data_inicio_input.text = datas_ordenadas[0]
            except: pass
            try:
                if not self.ids.filtro_data_fim_input.text.strip(): self.ids.filtro_data_fim_input.text = datas_ordenadas[-1]
            except: pass
        except Exception as e:
            logger.error(f"Erro carregar datas: {e}")

    def _atualizar_lista_vendas_comissao(self):
        try:
            if not hasattr(self.ids, 'vendas_comissao_list_box'): return
            box = self.ids.vendas_comissao_list_box
            box.clear_widgets()

            if not self.pedidos:
                box.add_widget(Label(text="Nenhuma venda até o momento", size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            for pedido in self.pedidos:
                container = BoxLayout(size_hint_y=None, height=45, padding=5, spacing=5, orientation="horizontal")
                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)
                    rect = Rectangle(size=container.size, pos=container.pos)
                container.bind(pos=lambda i, v: setattr(rect, 'pos', v), size=lambda i, v: setattr(rect, 'size', v))

                container.add_widget(Label(text=str(pedido.get('data_pedido', '-')), size_hint_x=0.2, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='center'))
                container.add_widget(Label(text=f"#{pedido.get('id')}", size_hint_x=0.15, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='center'))
                
                cliente_label = Label(text=pedido.get('cliente_nome', 'N/A'), size_hint_x=0.35, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='left')
                cliente_label.bind(size=lambda l, v: setattr(l, 'text_size', (v[0], v[1])))
                container.add_widget(cliente_label)

                valor_total = pedido.get('valor_total', pedido.get('total', 0))
                container.add_widget(Label(text=f"R$ {valor_total:.2f}", size_hint_x=0.3, font_size='11sp', bold=True, color=(0.2, 0.8, 0.2, 1), halign='right'))
                box.add_widget(container)
        except Exception as e:
            logger.error(f"Erro lista vendas: {e}")

    def calcular_comissao_percentual(self, percentual_texto: str):
        try:
            percentual_texto = (percentual_texto or "").strip()
            if not percentual_texto:
                try: self.ids.comissao_calculada_label.text = "R$ 0.00"
                except: pass
                return

            try:
                percentual = float(percentual_texto.replace(",", "."))
                if percentual < 0: self.log("❌ Porcentagem não pode ser negativa"); return
            except ValueError: return

            comissao_valor = self.total_vendas * percentual / 100
            try: self.ids.comissao_calculada_label.text = f"R$ {comissao_valor:.2f}"
            except: pass
            self.comissao = comissao_valor
        except Exception as e:
            logger.error(f"Erro percentual comissão: {e}")

    def salvar_comissao_vendedor(self):
        try:
            if not self.vendedor.get('nome'): self.log("Vendedor não está logado"); return

            recebimentos = []
            for i in range(1, 5):
                data_campo = f"recebimento_{i}_data_input"
                valor_campo = f"recebimento_{i}_valor_input"

                if not hasattr(self.ids, data_campo) or not hasattr(self.ids, valor_campo): continue

                data = self.ids[data_campo].text.strip()
                valor_str = self.ids[valor_campo].text.strip()

                if data and valor_str:
                    try:
                        valor = float(valor_str.replace(",", "."))
                        if valor < 0: self.log(f"❌ Valor do {i}º recebimento não pode ser negativo"); return
                        recebimentos.append({"numero": i, "data": data, "valor": valor})
                    except ValueError:
                        self.log(f"❌ Valor inválido no {i}º recebimento"); return
                elif data or valor_str:
                    self.log(f"❌ Preencha data e valor do {i}º recebimento"); return

            total_recebimentos = sum(r['valor'] for r in recebimentos)
            msg = f"✅ Comissão de {self.comissao:.2f} registrada"
            if recebimentos:
                msg += f" com {len(recebimentos)} recebimento(s) programado(s) (Total: R$ {total_recebimentos:.2f})"
            self.log(msg)

            for i in range(1, 5):
                try:
                    self.ids[f"recebimento_{i}_data_input"].text = ""
                    self.ids[f"recebimento_{i}_valor_input"].text = ""
                except: pass
        except Exception as e:
            logger.error(f"Erro salvar comissão: {e}")
            self.log(f"Erro ao salvar comissão: {e}")

    def filtrar_vendas_por_periodo(self):
        try:
            data_inicio_str = self.ids.filtro_data_inicio_label.text.strip() if hasattr(self.ids, 'filtro_data_inicio_label') else ""
            data_fim_str = self.ids.filtro_data_fim_label.text.strip() if hasattr(self.ids, 'filtro_data_fim_label') else ""

            if (not data_inicio_str or data_inicio_str == "--/--/----") and (not data_fim_str or data_fim_str == "--/--/----"):
                self.atualizar_comissao_vendedor()
                self._atualizar_lista_vendas_comissao()
                return

            if (not data_inicio_str or data_inicio_str == "--/--/----") or (not data_fim_str or data_fim_str == "--/--/----"):
                self.log("❌ Preencha AMBAS as datas"); return

            data_inicio = self._converter_data(data_inicio_str)
            data_fim = self._converter_data(data_fim_str)

            if not data_inicio or not data_fim:
                self.log(f"❌ Formato de data inválido"); return

            if data_inicio > data_fim:
                self.log("❌ Data inicial não pode ser maior que data final"); return

            pedidos_filtrados = [p for p in self.pedidos if (data_pedido := self._converter_data(p.get('data_pedido', ''))) and data_inicio <= data_pedido <= data_fim]

            total_filtrado = sum(p.get('valor_total', 0) for p in pedidos_filtrados)
            commission = total_filtrado * 0.05 if total_filtrado <= 50000 else 50000 * 0.05 + (total_filtrado - 50000) * 0.06

            try: self.ids.total_vendas_label.text = f"R$ {total_filtrado:.2f}"
            except: pass
            try: self.ids.comissao_label.text = f"R$ {commission:.2f}"
            except: pass

            self.log(f"✅ {len(pedidos_filtrados)} venda(s) encontrada(s)")

            if hasattr(self.ids, 'vendas_comissao_list_box'):
                box = self.ids.vendas_comissao_list_box
                box.clear_widgets()

                if not pedidos_filtrados:
                    box.add_widget(Label(text="Nenhuma venda neste período", size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                else:
                    for pedido in pedidos_filtrados:
                        container = BoxLayout(size_hint_y=None, height=45, padding=5, spacing=5, orientation="horizontal")
                        container.canvas.before.clear()
                        with container.canvas.before:
                            Color(0.98, 0.98, 1, 1)
                            rect = Rectangle(size=container.size, pos=container.pos)
                        container.bind(pos=lambda i, v: setattr(rect, 'pos', v), size=lambda i, v: setattr(rect, 'size', v))

                        container.add_widget(Label(text=str(pedido.get('data_pedido', '-')), size_hint_x=0.2, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='center'))
                        container.add_widget(Label(text=f"#{pedido.get('id')}", size_hint_x=0.15, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='center'))
                        
                        cliente_label = Label(text=pedido.get('cliente_nome', 'N/A'), size_hint_x=0.35, font_size='11sp', color=(0.1, 0.1, 0.1, 1), halign='left')
                        cliente_label.bind(size=lambda l, v: setattr(l, 'text_size', (v[0], v[1])))
                        container.add_widget(cliente_label)

                        container.add_widget(Label(text=f"R$ {pedido.get('valor_total', 0):.2f}", size_hint_x=0.3, font_size='11sp', bold=True, color=(0.2, 0.8, 0.2, 1), halign='right'))
                        box.add_widget(container)
        except Exception as e:
            logger.error(f"Erro filtrar período: {e}")
            self.log(f"❌ Erro: {e}")

    def abrir_calendario_inicio(self): self._abrir_calendario('inicio')
    def abrir_calendario_fim(self): self._abrir_calendario('fim')

    def _abrir_calendario(self, tipo_data: str):
        try:
            calendario_layout = BoxLayout(orientation='vertical', padding=5, spacing=2, size_hint_y=None, height="200dp")

            header_layout = BoxLayout(size_hint_y=None, height="25dp", spacing=3)
            btn_anterior = Button(text="◀", size_hint_x=0.3, font_size='10sp')
            self.mes_ano_label = Label(text=f"{self._nome_mes(self.calendario_mes)}/{self.calendario_ano}", size_hint_x=0.4, bold=True, font_size='11sp')
            btn_proximo = Button(text="▶", size_hint_x=0.3, font_size='10sp')

            btn_anterior.bind(on_press=lambda b: self._navegar_mes(-1, tipo_data))
            btn_proximo.bind(on_press=lambda b: self._navegar_mes(1, tipo_data))

            header_layout.add_widget(btn_anterior)
            header_layout.add_widget(self.mes_ano_label)
            header_layout.add_widget(btn_proximo)
            calendario_layout.add_widget(header_layout)

            dias_semana_layout = GridLayout(cols=7, size_hint_y=None, height="18dp", spacing=1)
            for dia in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']:
                dias_semana_layout.add_widget(Label(text=dia, color=(0.4, 0.4, 0.4, 1), bold=True, font_size='8sp'))
            calendario_layout.add_widget(dias_semana_layout)

            self.dias_grid = GridLayout(cols=7, size_hint_y=None, height="110dp", spacing=1)
            self._atualizar_dias_calendario(tipo_data)
            calendario_layout.add_widget(self.dias_grid)

            btn_limpar = Button(text="Limpar", size_hint_y=None, height="25dp", background_color=(0.8, 0.2, 0.2, 1), font_size='10sp')
            btn_limpar.bind(on_press=lambda b: self._limpar_filtro_periodo())
            calendario_layout.add_widget(btn_limpar)

            self.calendario_popup = Popup(title=f"Selecionar Data {'Inicial' if tipo_data == 'inicio' else 'Final'}", content=calendario_layout, size_hint=(0.6, 0.45))
            self.calendario_popup.open()
        except Exception as e:
            logger.error(f"Erro abrir calendário: {e}")

    def _navegar_mes(self, direcao: int, tipo_data: str):
        try:
            self.calendario_mes += direcao
            if self.calendario_mes > 12: self.calendario_mes = 1; self.calendario_ano += 1
            elif self.calendario_mes < 1: self.calendario_mes = 12; self.calendario_ano -= 1

            if hasattr(self, 'mes_ano_label'):
                self.mes_ano_label.text = f"{self._nome_mes(self.calendario_mes)}/{self.calendario_ano}"
            self._atualizar_dias_calendario(tipo_data)
        except Exception as e:
            logger.error(f"Erro navegar mês: {e}")

    def _atualizar_dias_calendario(self, tipo_data: str):
        try:
            if hasattr(self, 'dias_grid'):
                self.dias_grid.clear_widgets()

                primeiro_dia = datetime(self.calendario_ano, self.calendario_mes, 1)
                dia_semana_inicio = primeiro_dia.weekday()
                num_dias = self._num_dias_mes(self.calendario_mes, self.calendario_ano)

                for _ in range(dia_semana_inicio):
                    self.dias_grid.add_widget(Label())

                for dia in range(1, num_dias + 1):
                    btn_dia = Button(text=str(dia), size_hint_y=None, height="18dp", background_color=(0.9, 0.9, 0.9, 1), color=(0, 0, 0, 1), font_size='9sp')
                    btn_dia.bind(on_press=lambda b, d=dia, m=self.calendario_mes, a=self.calendario_ano, t=tipo_data: self._selecionar_data_calendario(d, m, a, t))
                    self.dias_grid.add_widget(btn_dia)
        except Exception as e:
            logger.error(f"Erro atualizar dias: {e}")

    def _nome_mes(self, mes: int) -> str:
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        return meses[mes - 1] if 1 <= mes <= 12 else ''

    def _num_dias_mes(self, mes: int, ano: int) -> int:
        if mes in [1, 3, 5, 7, 8, 10, 12]: return 31
        elif mes in [4, 6, 9, 11]: return 30
        elif mes == 2: return 29 if (ano % 4 == 0 and ano % 100 != 0) or (ano % 400 == 0) else 28
        return 0

    def _selecionar_data_calendario(self, dia: int, mes: int, ano: int, tipo_data: str):
        try:
            data_formatada = f"{dia:02d}/{mes:02d}/{ano}"
            if tipo_data == 'inicio':
                try: self.ids.filtro_data_inicio_label.text = data_formatada
                except: pass
            else:
                try: self.ids.filtro_data_fim_label.text = data_formatada
                except: pass

            try:
                from kivy.app import App
                root_window = App.get_running_app().root_window
                for child in list(root_window.children):
                    if isinstance(child, Popup): child.dismiss()
            except: pass
        except Exception as e:
            logger.error(f"Erro selecionar data: {e}")

    def _limpar_filtro_periodo(self):
        try:
            try: self.ids.filtro_data_inicio_label.text = "--/--/----"
            except: pass
            try: self.ids.filtro_data_fim_label.text = "--/--/----"
            except: pass

            try:
                from kivy.app import App
                root_window = App.get_running_app().root_window
                for child in list(root_window.children):
                    if isinstance(child, Popup): child.dismiss()
            except: pass

            self.filtrar_vendas_por_periodo()
        except Exception as e:
            logger.error(f"Erro limpar filtro: {e}")

    # ==================== ITENS/VENDA ====================
    def incrementar_quantidade(self):
        try:
            qtd_atual = float(self.ids.quantidade_input.text or "0")
            self.ids.quantidade_input.text = str(int(qtd_atual + 1))
        except ValueError:
            self.ids.quantidade_input.text = "1"

    def decrementar_quantidade(self):
        try:
            qtd_atual = float(self.ids.quantidade_input.text or "0")
            self.ids.quantidade_input.text = str(int(max(1, qtd_atual - 1)))
        except ValueError:
            self.ids.quantidade_input.text = "1"

    def mostrar_sugestoes_cliente(self, textinput, mostrar: bool):
        try:
            scroll = self.ids.clientes_sugestoes_scroll
            lista = self.ids.clientes_sugestoes_list

            if mostrar and textinput.focus:
                lista.clear_widgets()
                texto = textinput.text.strip().lower()
                sugestoes = [c for c in self.clientes if texto in str(c.get('nome', '')).lower() or texto in str(c.get('id', '')).lower()] if texto else self.clientes[:10]

                for cliente in sugestoes:
                    btn = Button(text=f"{cliente['id']} - {cliente['nome']}", size_hint_y=None, height="40dp", background_color=(0.01, 0.45, 0.89, 1), color=(1, 1, 1, 1), font_size="12sp", halign="left")
                    btn.bind(on_release=lambda b, c=cliente: self.selecionar_cliente_sugestao(c, textinput))
                    lista.add_widget(btn)

                altura = min(len(sugestoes) * 41, 200) if sugestoes else 0
                scroll.height = altura
                scroll.opacity = 1 if sugestoes else 0
            else:
                scroll.height = 0
                scroll.opacity = 0
        except Exception as e:
            logger.error(f"Erro sugestões cliente: {e}")

    def mostrar_sugestoes_produto(self, textinput, mostrar: bool):
        try:
            scroll = self.ids.produtos_sugestoes_scroll
            lista = self.ids.produtos_sugestoes_list

            if mostrar and textinput.focus:
                lista.clear_widgets()
                texto = textinput.text.strip().lower()
                sugestoes = [p for p in self.produtos if texto in str(p.get('nome', '')).lower() or texto in str(p.get('id', '')).lower()] if texto else self.produtos[:10]

                from produtos import listar_precos_variaveis
                for produto in sugestoes:
                    estoque = float(produto.get('estoque', 0))
                    sem_estoque = estoque > 0 and estoque <= 0
                    cor_fundo = (0.8, 0.2, 0.2, 1) if sem_estoque else (0.01, 0.45, 0.89, 1)

                    variacoes = listar_precos_variaveis(produto.get('id', 0))
                    preco_base = float(produto.get('preco', 0))

                    if variacoes:
                        primeira_var = variacoes[0]
                        qtd_var = int(primeira_var.get('quantidade_min', 0))
                        preco_var = primeira_var.get('preco', 0)
                        texto_preco = f"R$ {preco_base:.2f} | {qtd_var}+ R$ {preco_var:.2f}" + ("..." if len(variacoes) > 1 else "")
                    else:
                        texto_preco = f"R$ {preco_base:.2f}"

                    texto_completo = f"{produto['id']} - {produto['nome']}\n{texto_preco}"

                    btn = Button(text=texto_completo, size_hint_y=None, height="50dp", background_color=cor_fundo, color=(1, 1, 1, 1), font_size="11sp", halign="left", valign="middle")
                    btn.bind(on_release=lambda b, p=produto: self.selecionar_produto_sugestao(p, textinput))
                    lista.add_widget(btn)

                altura = min(len(sugestoes) * 51, 200) if sugestoes else 0
                scroll.height = altura
                scroll.opacity = 1 if sugestoes else 0
            else:
                scroll.height = 0
                scroll.opacity = 0
        except Exception as e:
            logger.error(f"Erro sugestões produto: {e}")

    def selecionar_cliente_sugestao(self, cliente: Dict, textinput):
        try:
            self.cliente_selecionado = cliente
            textinput.text = f"{cliente['id']} - {cliente['nome']}"
            self.log(f"✓ Cliente: {cliente['nome']} (ID: {cliente['id']})")
            self.mostrar_sugestoes_cliente(textinput, False)
        except Exception as e:
            logger.error(f"Erro selecionar cliente: {e}")

    def selecionar_produto_sugestao(self, produto: Dict, textinput):
        try:
            self.produto_selecionado = produto
            textinput.text = f"{produto['id']} - {produto['nome']}"
            self.log(f"✓ Produto: {produto['nome']} (ID: {produto['id']})")
            self.mostrar_sugestoes_produto(textinput, False)
        except Exception as e:
            logger.error(f"Erro selecionar produto: {e}")

    def buscar_cliente_autocomplete(self, texto: str):
        try:
            if not texto.strip().lower():
                self.log("Digite o nome ou ID do cliente")
                self.mostrar_sugestoes_cliente(self.ids.clientes_search, self.ids.clientes_search.focus)
                return
            self.mostrar_sugestoes_cliente(self.ids.clientes_search, self.ids.clientes_search.focus)
        except Exception as e:
            logger.error(f"Erro busca cliente: {e}")

    def buscar_produto_autocomplete(self, texto: str):
        try:
            if not texto.strip().lower():
                self.log("Digite o nome ou ID do produto")
                self.mostrar_sugestoes_produto(self.ids.produtos_search, self.ids.produtos_search.focus)
                return
            self.mostrar_sugestoes_produto(self.ids.produtos_search, self.ids.produtos_search.focus)
        except Exception as e:
            logger.error(f"Erro busca produto: {e}")

    def add_item_to_pedido(self):
        try:
            if not self.produtos: self.reload_data()

            produto = self.produto_selecionado
            if not produto:
                texto = (self.ids.produtos_search.text or "").strip().lower()
                if texto:
                    for p in self.produtos:
                        if texto in str(p.get('nome', '')).lower() or texto in str(p.get('id', '')).lower():
                            produto = p
                            break

            if not produto: self.log("❌ Selecione um produto clicando nas sugestões"); return

            try:
                qtd = float(self.ids.quantidade_input.text or DEFAULT_QUANTITY)
            except ValueError:
                qtd = DEFAULT_QUANTITY

            qtd = max(1, qtd)

            if not self.venda.adicionar_item(produto, qtd):
                estoque = float(produto.get('estoque', 0))
                self.log(f"❌ Estoque insuficiente! Disponível: {estoque}" if estoque > 0 else "❌ Erro ao adicionar produto")
                return

            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()

            self.ids.produtos_search.text = ""
            self.ids.quantidade_input.text = str(int(DEFAULT_QUANTITY))
            self.produto_selecionado = None

            self.log(f"✓ {produto['nome']} adicionado")
        except Exception as e:
            logger.error(f"Erro add item: {e}")
            self.log(f"Erro ao adicionar item: {e}")

    def atualizar_lista_itens(self):
        box = self.ids.itens_box
        box.clear_widgets()

        for i, item in enumerate(self.venda.itens):
            container = BoxLayout(size_hint_y=None, height=50, padding=5, spacing=5)
            container.canvas.before.clear()
            with container.canvas.before:
                Color(1, 1, 1, 1)
                rect = Rectangle(size=container.size, pos=container.pos)
            container.bind(pos=lambda inst, v: setattr(rect, 'pos', v), size=lambda inst, v: setattr(rect, 'size', v))

            quantidade_input = TextInput(text=str(int(item['quantidade']) if item['quantidade'].is_integer() else item['quantidade']), size_hint_x=0.15, size_hint_y=None, height=40, multiline=False, input_filter="float", halign="center", font_size="14sp")
            quantidade_input.bind(text=lambda inst, v, idx=i: self.alterar_quantidade_item(idx, v))

            container.add_widget(quantidade_input)
            container.add_widget(Label(text=item['produto_nome'], size_hint_x=0.5, color=(0.2, 0.2, 0.2, 1), font_size="14sp", halign="left"))
            container.add_widget(Label(text=f"R$ {item['preco_unitario']:.2f}", size_hint_x=0.15, color=(0.2, 0.2, 0.2, 1), font_size="14sp", halign="center"))
            container.add_widget(Label(text=f"R$ {item['total']:.2f}", size_hint_x=0.15, color=(0.2, 0.2, 0.2, 1), font_size="14sp", bold=True, halign="center"))

            btn = self._criar_botao("❌", 0.05, altura=40, cor=(0.9, 0.3, 0.3, 1), callback=lambda b, idx=i: self.remover_item(idx))
            container.add_widget(btn)
            box.add_widget(container)

    def atualizar_resumo_itens(self):
        try:
            if not self.venda.itens:
                self.ids.itens_resumo.text = "Nenhum item adicionado"
            else:
                resumo = [f"{item['produto_nome']} ({item['quantidade']}x)" for item in self.venda.itens]
                self.ids.itens_resumo.text = "Itens: " + ", ".join(resumo)
        except: pass

    def remover_item(self, index: int):
        self.venda.remover_item(index)
        self.atualizar_lista_itens()
        self.atualizar_resumo_itens()
        self.update_total()

    def alterar_quantidade_item(self, index: int, nova_quantidade: str):
        try:
            qtd = float(nova_quantidade)
            if self.venda.alterar_quantidade(index, qtd):
                self.atualizar_lista_itens()
                self.atualizar_resumo_itens()
                self.update_total()
        except ValueError: pass

    def update_total(self):
        self.ids.pedido_total.text = f"TOTAL: R$ {self.venda.total:.2f}"

    def _limpar_campos_venda(self):
        try:
            self.ids.clientes_search.text = ""
            self.ids.produtos_search.text = ""
            self.ids.pagamento_spinner.text = "Dinheiro"
            self.ids.quantidade_input.text = "1"
            self.cliente_selecionado = None
            self.produto_selecionado = None
        except: pass

    def _limpar_pedido(self):
        try:
            self.venda = Venda()
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            self._limpar_campos_venda()
            self.log("Pedido limpo")
        except Exception as e:
            logger.error(f"Erro limpar pedido: {e}")

    def finalizar_venda(self):
        try:
            if not self.cliente_selecionado: self.log(ERROR_CLIENT_MUST_CHOOSE); return

            self.venda.definir_cliente(self.cliente_selecionado)
            self.venda.definir_pagamento(self.ids.pagamento_spinner.text)

            ok, result = self.venda.finalizar_venda()
            if not ok: self.log(result); return

            if isinstance(result, dict) and 'pedido_id' in result:
                self.last_pedido_id = result['pedido_id']

            self.venda = Venda()
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            self._limpar_campos_venda()
            self.carregar_pedidos()
            self.reload_data()

            self.log(SUCCESS_VENDA_FINALIZED)
            self._mostrar_popup_compartilhar(self.last_pedido_id)
        except Exception as e:
            logger.error(f"Erro finalizar venda: {e}")
            self.log(LOG_VENDA_ERROR.format(e))

    def on_tab_venda_enter(self):
        try:
            self.reload_data()
        except Exception as e:
            logger.error(f"Erro tab venda: {e}")

    def on_tab_comissao_enter(self):
        try:
            self.carregar_datas_comissao()
        except Exception as e:
            logger.error(f"Erro tab comissão: {e}")

    # ==================== AUTENTICAÇÃO ====================
    def fazer_login(self):
        try:
            username = self._get_texto("login_usuario_input")
            senha = self._get_texto("login_senha_input")

            if not username or not senha: self.ids.login_erro_label.text = "Usuário e senha obrigatórios"; return

            resultado = verificar_login(username, senha)

            if resultado["sucesso"]:
                self.ids.login_usuario_input.text = ""
                self.ids.login_senha_input.text = ""
                self.ids.login_erro_label.text = ""

                self.usuario_logado = resultado["usuario"]
                try: self.ids.vendedor_label.text = f"Vendedor: {self.usuario_logado.get('nome_completo', 'N/A')}"
                except: pass
                self.log(f"Bem-vindo, {resultado['usuario']['nome_completo']}")

                self.reload_data()
                self.carregar_pedidos()

                if not self.usuario_logado.get('usa_biometria', False):
                    self._pergunta_usar_digital()
                else:
                    self._mostrar_telas_trabalho()
            else:
                self.ids.login_erro_label.text = resultado["mensagem"]
        except Exception as e:
            logger.error(f"Erro login: {e}")
            self.ids.login_erro_label.text = f"Erro ao fazer login: {e}"

    def fazer_cadastro(self):
        try:
            username = self._get_texto("cadastro_usuario_input")
            email = self._get_texto("cadastro_email_input")
            nome = self._get_texto("cadastro_nome_input")
            senha = self._get_texto("cadastro_senha_input")
            senha_confirma = self._get_texto("cadastro_senha_confirma_input")
            usa_biometria = self.ids.cadastro_biometria_check.active

            if not all([username, email, nome, senha, senha_confirma]):
                self.ids.cadastro_mensagem_label.text = "Todos os campos são obrigatórios"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                return

            if "@" not in email or "." not in email:
                self.ids.cadastro_mensagem_label.text = "Email inválido"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                return

            if senha != senha_confirma:
                self.ids.cadastro_mensagem_label.text = "As senhas não conferem"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                return

            if len(senha) < 4:
                self.ids.cadastro_mensagem_label.text = "Senha deve ter no mínimo 4 caracteres"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                return

            if usuario_existe(username):
                self.ids.cadastro_mensagem_label.text = "Este usuário já existe"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                return

            resultado = add_usuario(username, email, senha, nome, usa_biometria)

            if resultado["sucesso"]:
                msg_biometria = " com autenticação por digital habilitada" if usa_biometria else ""
                self.ids.cadastro_mensagem_label.text = f"✓ Conta criada{msg_biometria}! Faça login."
                self.ids.cadastro_mensagem_label.color = (0, 1, 0, 1)

                for campo in ["cadastro_usuario_input", "cadastro_email_input", "cadastro_nome_input", "cadastro_senha_input", "cadastro_senha_confirma_input"]:
                    try: self.ids[campo].text = ""
                    except: pass
                self.ids.cadastro_biometria_check.active = False

                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.ir_para_login(), 2)
            else:
                self.ids.cadastro_mensagem_label.text = resultado["mensagem"]
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
        except Exception as e:
            logger.error(f"Erro cadastro: {e}")
            self.ids.cadastro_mensagem_label.text = f"Erro ao cadastrar: {e}"
            self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)

    def login_com_digital(self):
        try:
            usuarios = listar_usuarios_com_biometria()
            if not usuarios: self.ids.login_erro_label.text = "Nenhum usuário com digital habilitada"; return

            if len(usuarios) == 1:
                self._autenticar_com_digital(usuarios[0])
            else:
                self.ids.login_erro_label.text = f"Usuários: {', '.join(usuarios)}"
        except Exception as e:
            logger.error(f"Erro login digital: {e}")
            self.ids.login_erro_label.text = f"Erro: {e}"

    def _autenticar_com_digital(self, username: str):
        try:
            if not verificar_biometria_habilitada(username): self.ids.login_erro_label.text = "Usuário sem biometria"; return

            conn = get_conn()
            user = conn.cursor().execute("SELECT id, username, nome_completo FROM usuarios WHERE username = ?", (username,)).fetchone()
            conn.close()

            if user:
                self.usuario_logado = dict(user)
                self.ids.login_usuario_input.text = ""
                self.ids.login_senha_input.text = ""
                self.ids.login_erro_label.text = ""
                try: self.ids.vendedor_label.text = f"Vendedor: {user['nome_completo']}"
                except: pass

                self.log(f"✓ Login com digital! Bem-vindo, {user['nome_completo']}")
                self.reload_data()
                self.carregar_pedidos()
                self._mostrar_telas_trabalho()
            else:
                self.ids.login_erro_label.text = "Erro ao autenticar"
        except Exception as e:
            logger.error(f"Erro autenticar digital: {e}")
            self.ids.login_erro_label.text = f"Erro: {e}"

    def ir_para_login(self):
        try:
            self.ids.tab_panel.switch_to(self.ids.login_tab)
            self.log("Faça login para continuar")
        except: pass

    def ir_para_cadastro(self):
        try:
            self.ids.tab_panel.switch_to(self.ids.cadastro_tab)
            self.log("Crie sua conta para começar")
        except: pass

    def _pergunta_usar_digital(self):
        try:
            box = BoxLayout(orientation='vertical', padding=10, spacing=10)
            box.add_widget(Label(text="Deseja usar autenticação por digital\npara próximos logins?", size_hint_y=0.6))

            botoes = BoxLayout(size_hint_y=0.4, spacing=10)
            popup = Popup(title="Autenticação Digital", content=box, size_hint=(0.8, 0.4))

            def habilitar():
                resultado = atualizar_biometria_usuario(self.usuario_logado.get('username', ''), True)
                if resultado['sucesso']:
                    self.log("Autenticação por digital habilitada!")
                    self.usuario_logado['usa_biometria'] = True
                popup.dismiss()
                self._mostrar_telas_trabalho()

            btn_sim = Button(text="Sim", background_color=(0.2, 0.7, 0.2, 1))
            btn_sim.bind(on_press=lambda x: habilitar())
            btn_nao = Button(text="Não", background_color=(0.7, 0.2, 0.2, 1))
            btn_nao.bind(on_press=lambda x: [popup.dismiss(), self._mostrar_telas_trabalho()])

            botoes.add_widget(btn_sim)
            botoes.add_widget(btn_nao)
            box.add_widget(botoes)
            popup.open()
        except Exception as e:
            logger.error(f"Erro popup digital: {e}")
            self._mostrar_telas_trabalho()

    def abrir_perfil(self):
        try:
            if not self.usuario_logado: return

            for campo, chave in [("perfil_usuario_input", 'username'), ("perfil_nome_input", 'nome_completo'), ("perfil_email_input", 'email')]:
                try: self.ids[campo].text = self.usuario_logado.get(chave, '')
                except: pass

            try: self.ids.perfil_digital_check.active = self.usuario_logado.get('usa_biometria', False)
            except: pass

            self.ids.tab_perfil.disabled = False
            self.ids.tab_panel.switch_to(self.ids.tab_perfil)
        except Exception as e:
            logger.error(f"Erro abrir perfil: {e}")

    def salvar_perfil(self):
        try:
            if not self.usuario_logado: return

            nome = self._get_texto("perfil_nome_input").strip()
            email = self._get_texto("perfil_email_input").strip()
            usa_biometria = self.ids.perfil_digital_check.active

            if not nome or not email: self.log("Nome e email são obrigatórios"); return

            resultado = atualizar_usuario(self.usuario_logado.get('id', 0), nome_completo=nome, email=email, usa_biometria=usa_biometria)

            if resultado["sucesso"]:
                self.usuario_logado['nome_completo'] = nome
                self.usuario_logado['email'] = email
                self.usuario_logado['usa_biometria'] = usa_biometria
                try: self.ids.vendedor_label.text = f"Vendedor: {nome}"
                except: pass
                self.log("Perfil atualizado com sucesso!")
            else:
                self.log(f"Erro: {resultado['mensagem']}")
        except Exception as e:
            logger.error(f"Erro salvar perfil: {e}")
            self.log(f"Erro ao salvar perfil: {e}")

    def fazer_logout(self):
        try:
            self.usuario_logado = None
            try: self.ids.vendedor_label.text = "Vendedor: -"
            except: pass
            self.log("Logout realizado")
            self._mostrar_telas_login()
        except Exception as e:
            logger.error(f"Erro logout: {e}")

    def fechar_perfil(self):
        try:
            self.ids.tab_perfil.disabled = True
            for aba_id in ["tab_clientes", "tab_produtos", "tab_venda"]:
                try:
                    if not self.ids[aba_id].disabled:
                        self.ids.tab_panel.switch_to(self.ids[aba_id])
                        break
                except: pass
        except Exception as e:
            logger.error(f"Erro fechar perfil: {e}")

    def _mostrar_telas_login(self):
        self._controlar_abas(habilitar_login=True)
        try: self.ids.tab_panel.switch_to(self.ids.login_tab)
        except: pass

    def _mostrar_telas_trabalho(self):
        self._controlar_abas(habilitar_login=False)
        try: self.ids.tab_panel.switch_to(self.ids.tab_clientes)
        except: pass

    # ==================== INVENTÁRIO ====================
    def atualizar_inventario(self):
        try:
            if hasattr(self.ids, 'inventario_list_box'): self._exibir_inventario()
            if hasattr(self.ids, 'mais_vendidos_list_box'): self._exibir_mais_vendidos()
            self.log("Inventário atualizado!")
        except Exception as e:
            logger.error(f"Erro inventário: {e}")
            self.log(f"Erro: {e}")

    def _exibir_inventario(self):
        try:
            if not hasattr(self.ids, 'inventario_list_box'): return
            box = self.ids.inventario_list_box
            box.clear_widgets()

            produtos = list_produtos()
            if not produtos:
                box.add_widget(Label(text="[b]Nenhum produto[/b]", markup=True, size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            # Cabeçalho
            header = BoxLayout(size_hint_y=None, height="35dp", spacing=5, padding=[5, 0])
            for texto, width in [("Produto", 0.4), ("Estoque", 0.2), ("Preço", 0.2), ("Valor Total", 0.2)]:
                header.add_widget(Label(text=f"[b]{texto}[/b]", markup=True, size_hint_x=width, bold=True, color=(0, 0, 0, 1), font_size="12sp"))
            box.add_widget(header)

            separator = Label(text="-" * 50, size_hint_y=None, height="20dp", color=(0.8, 0.8, 0.8, 1), halign="center")
            box.add_widget(separator)

            # Produtos
            total_valor = 0
            for produto in produtos:
                estoque = produto.get('estoque', 0)
                preco = produto.get('preco', 0)
                valor_total = estoque * preco
                total_valor += valor_total

                item_box = BoxLayout(size_hint_y=None, height="30dp", spacing=5, padding=[5, 0])
                item_box.add_widget(Label(text=produto.get('nome', ''), size_hint_x=0.4, color=(1, 0, 0, 1) if estoque == 0 else (0, 0, 0, 1), font_size="11sp", bold=estoque == 0))
                item_box.add_widget(Label(text=str(estoque), size_hint_x=0.2, color=(0, 0, 0, 1), font_size="11sp", halign="center"))
                item_box.add_widget(Label(text=f"R$ {preco:.2f}", size_hint_x=0.2, color=(0, 0, 0, 1), font_size="11sp", halign="center"))
                item_box.add_widget(Label(text=f"R$ {valor_total:.2f}", size_hint_x=0.2, color=(0, 0, 0, 1), font_size="11sp", halign="center"))
                box.add_widget(item_box)

            # Total
            total_box = BoxLayout(size_hint_y=None, height="35dp", spacing=5, padding=[5, 5])
            total_box.add_widget(Label(text="[b]TOTAL:[/b]", markup=True, size_hint_x=0.8, color=(0, 0.5, 0, 1), bold=True, font_size="13sp"))
            total_box.add_widget(Label(text=f"[b]R$ {total_valor:.2f}[/b]", markup=True, size_hint_x=0.2, color=(0, 0.5, 0, 1), bold=True, font_size="13sp", halign="right"))
            box.add_widget(total_box)
        except Exception as e:
            logger.error(f"Erro exibir inventário: {e}")

    def _exibir_mais_vendidos(self):
        try:
            if not hasattr(self.ids, 'mais_vendidos_list_box'): return
            box = self.ids.mais_vendidos_list_box
            box.clear_widgets()

            vendas_por_produto = self._calcular_vendas_por_produto()
            if not vendas_por_produto:
                box.add_widget(Label(text="[b]Nenhuma venda[/b]", markup=True, size_hint_y=None, height="40dp", color=(0.5, 0.5, 0.5, 1)))
                return

            vendas_ordenadas = sorted(vendas_por_produto.items(), key=lambda x: x[1]['valor_total'], reverse=True)

            # Cabeçalho (simplificado)
            header = BoxLayout(size_hint_y=None, height="35dp", spacing=5, padding=[5, 0])
            for texto, width in [("Produto", 0.4), ("Qtd", 0.2), ("Valor Total", 0.4)]:
                header.add_widget(Label(text=f"[b]{texto}[/b]", markup=True, size_hint_x=width, bold=True, color=(0, 0, 0, 1), font_size="12sp"))
            box.add_widget(header)

            for produto_nome, dados in vendas_ordenadas[:10]:
                item_box = BoxLayout(size_hint_y=None, height="30dp", spacing=5, padding=[5, 0])
                item_box.add_widget(Label(text=produto_nome, size_hint_x=0.4, color=(0, 0, 0, 1), font_size="11sp"))
                item_box.add_widget(Label(text=f"{dados['quantidade']:.0f}", size_hint_x=0.2, color=(0, 0, 0, 1), font_size="11sp", halign="center"))
                item_box.add_widget(Label(text=f"R$ {dados['valor_total']:.2f}", size_hint_x=0.4, color=(0, 0.6, 0, 1), font_size="11sp", halign="right"))
                box.add_widget(item_box)
        except Exception as e:
            logger.error(f"Erro mais vendidos: {e}")

    def _calcular_vendas_por_produto(self) -> Dict[str, Dict]:
        """Calcula total vendido por produto."""
        vendas = {}
        for pedido in self.pedidos:
            for item in get_itens_pedido(pedido['id']):
                nome = item.get('produto_nome', 'N/A')
                if nome not in vendas:
                    vendas[nome] = {'quantidade': 0, 'valor_total': 0}
                vendas[nome]['quantidade'] += item.get('quantidade', 0)
                vendas[nome]['valor_total'] += item.get('quantidade', 0) * item.get('preco_unitario', 0)
        return vendas

# Exports para uso em outras partes
def build():
    return RootWidget()
