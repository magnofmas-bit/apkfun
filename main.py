"""
main.py - Módulo principal da aplicação Kivy para controle de vendas.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty, StringProperty, DictProperty, NumericProperty
from kivy.uix.popup import Popup

import requests
import logging
import os
import socket
from typing import Optional, Dict, Any, List

from vendas import Venda
from db import init_db, list_clientes, add_cliente, list_produtos, add_produto, list_pedidos, get_itens_pedido, update_pedido_status, add_usuario, verificar_login, usuario_existe, verificar_biometria_habilitada, listar_usuarios_com_biometria, atualizar_biometria_usuario, atualizar_usuario, get_conn
from clientes import editar_cliente as editar_cliente_db
from constants import (
    PLACEHOLDER_CHOOSE,
    DEFAULT_QUANTITY,
    ERROR_CEP_INVALID,
    ERROR_CEP_NOT_FOUND,
    ERROR_CLIENT_REQUIRED,
    ERROR_PRODUCT_REQUIRED,
    ERROR_PRODUCT_NOT_FOUND,
    ERROR_CLIENT_NOT_FOUND,
    ERROR_CLIENT_MUST_CHOOSE,
    ERROR_PRODUCT_MUST_CHOOSE,
    SUCCESS_CLIENTE_ADDED,
    SUCCESS_PRODUTO_ADDED,
    SUCCESS_ENDEREÇO_FILLED,
    SUCCESS_VENDA_FINALIZED,
    LOG_RELOAD_ERROR,
    LOG_CEP_ERROR,
    LOG_CLIENTE_ERROR,
    LOG_PRODUTO_ERROR,
    LOG_ITEM_ERROR,
    LOG_VENDA_ERROR,
    CEP_LENGTH,
    CEP_API_URL,
    CEP_TIMEOUT,
)

logger = logging.getLogger(__name__)


class RootWidget(BoxLayout):
    """Widget raiz da aplicação de controle de vendas."""

    clientes = ListProperty([])
    produtos = ListProperty([])
    clientes_spinner_values = ListProperty([])
    produtos_spinner_values = ListProperty([])
    status_log = StringProperty("Iniciado")
    pedidos = ListProperty([])
    vendedor = DictProperty({})  # Dados do vendedor
    total_vendas = NumericProperty(0.0)  # Total de vendas
    comissao = NumericProperty(0.0)  # Comissão calculada

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.venda = Venda()
        self.cliente_selecionado = None
        self.produto_selecionado = None
        self.usuario_logado = None  # Usuário autenticado
        self.cliente_em_edicao_id = None

    def on_kv_post(self, *args):
        """Chamado após carregar arquivo KV."""
        # Inicializar estado de abas: mostrar login/cadastro e ocultar abas de trabalho.
        self._mostrar_telas_login()

        # Forçar seleção da aba de login (evitar painel cinza sem aba selecionada).
        try:
            if hasattr(self.ids, 'tab_panel') and hasattr(self.ids, 'login_tab'):
                self.ids.login_tab.disabled = False
                if hasattr(self.ids, 'cadastro_tab'):
                    self.ids.cadastro_tab.disabled = False

                tab_panel = self.ids.tab_panel
                login_tab = self.ids.login_tab

                tab_panel.default_tab = login_tab
                tab_panel.switch_to(login_tab)

                print("[on_kv_post] Aba de login forçada com switch_to()")
            else:
                print("[on_kv_post] Abas não encontradas (não foi possível forçar login)")

        except Exception as e:
            print(f"[on_kv_post] Erro forçando aba de login: {e}")
            import traceback
            traceback.print_exc()

        # Se falhar, fallback para desabilitar abas e manter ao menos login visível.
        try:
            if not hasattr(self.ids, 'tab_panel'):
                self._desabilitar_abas_trabalho()
        except Exception:
            self._desabilitar_abas_trabalho()

        # Carregar dados iniciais (produtos, clientes, pedidos)
        try:
            self.reload_data()
            self.carregar_pedidos()
            logger.info("Dados iniciais carregados ao iniciar a interface")
        except Exception as e:
            logger.error(f"Erro ao carregar dados iniciais: {e}")


    def reload_data(self) -> None:
        """Carrega dados de clientes e produtos do banco de dados."""
        try:
            self.clientes = list_clientes()
            self.produtos = list_produtos()

            # Preparar lista de clientes para spinner
            self.clientes_spinner_values = [PLACEHOLDER_CHOOSE] + [
                f"{c['id']} - {c['nome']}" for c in self.clientes
            ]

            # Preparar lista de produtos para spinner
            self.produtos_spinner_values = [PLACEHOLDER_CHOOSE] + [
                f"{p['id']} - {p['nome']}" for p in self.produtos
            ]

            logger.info(f"Dados recarregados: {len(self.produtos)} produtos, {len(self.clientes)} clientes")
            
            # Atualizar lista de produtos se a aba já foi carregada
            try:
                self.atualizar_lista_produtos()
            except Exception as e:
                logger.debug(f"Ainda não é possível atualizar lista de produtos: {e}")

        except Exception as e:
            logger.error(f"Erro ao recarregar dados: {e}")
            self.log(LOG_RELOAD_ERROR.format(e))

    def carregar_pedidos(self) -> None:
        """Carrega lista de pedidos do banco de dados e exibe na aba Pedidos."""
        try:
            self.pedidos = list_pedidos()
            self._atualizar_lista_pedidos()
            self._atualizar_lista_vendas_comissao()
            self.atualizar_comissao_vendedor()
            logger.info(f"Carregados {len(self.pedidos)} pedidos")
        except Exception as e:
            logger.error(f"Erro ao carregar pedidos: {e}")
            self.log(f"Erro ao carregar pedidos: {e}")

    def _atualizar_lista_pedidos(self) -> None:
        """Atualiza a visualização dos pedidos finalizados em formato de tabela."""
        try:
            box = self.ids.pedidos_list_box
            box.clear_widgets()

            # Obter pedidos filtrados
            pedidos_filtrados = self._get_pedidos_filtrados()

            if not pedidos_filtrados:
                box.add_widget(Label(
                    text="Nenhum pedido encontrado",
                    size_hint_y=None,
                    height="40dp",
                    font_size="14sp",
                    color=(0.5, 0.5, 0.5, 1)
                ))
                return

            # Cabeçalho da tabela
            header_layout = BoxLayout(
                size_hint_y=None,
                height="40dp",
                spacing=1,
                padding=[5, 5, 5, 5]
            )
            
            headers = ["ID", "Cliente", "Data", "Produtos", "Total", "Ações"]
            header_widths = [0.1, 0.25, 0.15, 0.3, 0.12, 0.08]
            
            for header, width in zip(headers, header_widths):
                header_label = Label(
                    text=f"[b]{header}[/b]",
                    markup=True,
                    size_hint_x=width,
                    font_size="12sp",
                    bold=True,
                    color=(0.2, 0.2, 0.2, 1),
                    halign="center"
                )
                header_layout.add_widget(header_label)
            
            box.add_widget(header_layout)

            # Linha separadora
            separator = BoxLayout(size_hint_y=None, height="2dp", spacing=1)
            for _ in headers:
                sep = Label(size_hint_y=None, height="2dp")
                sep.canvas.before.clear()
                with sep.canvas.before:
                    Color(0.8, 0.8, 0.8, 1)
                    Rectangle(pos=sep.pos, size=sep.size)
                separator.add_widget(sep)
            box.add_widget(separator)

            # Linhas de dados
            for pedido in pedidos_filtrados:
                row_layout = BoxLayout(
                    size_hint_y=None,
                    height="35dp",
                    spacing=1,
                    padding=[5, 2, 5, 2]
                )
                
                # Fundo alternado para linhas
                row_color = (0.98, 0.98, 0.98, 1) if len(box.children) % 2 == 0 else (1, 1, 1, 1)
                row_layout.canvas.before.clear()
                with row_layout.canvas.before:
                    Color(*row_color)
                    Rectangle(pos=row_layout.pos, size=row_layout.size)
                
                # ID do pedido
                id_label = Label(
                    text=str(pedido['id']),
                    size_hint_x=0.1,
                    font_size="11sp",
                    halign="center",
                    color=(0.3, 0.3, 0.3, 1)
                )
                row_layout.add_widget(id_label)
                
                # Cliente
                cliente_nome = pedido.get('cliente_nome', 'N/A')
                cliente_label = Label(
                    text=cliente_nome,
                    size_hint_x=0.25,
                    font_size="11sp",
                    halign="left",
                    color=(0.2, 0.2, 0.2, 1)
                )
                row_layout.add_widget(cliente_label)
                
                # Data + hora
                data_pedido = pedido.get('data_pedido', '')
                data_formatada = 'N/A'
                hora_formatada = ''

                if data_pedido:
                    try:
                        from datetime import datetime
                        data_obj = datetime.fromisoformat(data_pedido.replace('Z', '+00:00'))
                        data_formatada = data_obj.strftime('%d/%m/%Y')
                        hora_formatada = data_obj.strftime('%H:%M:%S')
                    except Exception:
                        # caso a entrada já esteja em formato SQL 'YYYY-MM-DD HH:MM:SS'
                        try:
                            data_str, hora_str = data_pedido.split(' ')
                            yyyy, mm, dd = data_str.split('-')
                            data_formatada = f"{dd}/{mm}/{yyyy}"
                            hora_formatada = hora_str
                        except Exception:
                            data_formatada = data_pedido[:10] if len(data_pedido) >= 10 else data_pedido
                            hora_formatada = data_pedido[11:19] if len(data_pedido) >= 19 else ''

                data_label = Label(
                    text=f"{hora_formatada} {data_formatada}" if hora_formatada else data_formatada,
                    size_hint_x=0.2,
                    font_size="11sp",
                    halign="center",
                    color=(0.3, 0.3, 0.3, 1)
                )
                row_layout.add_widget(data_label)
                
                # Produtos (resumo)
                itens = get_itens_pedido(pedido['id'])
                produtos_texto = ""
                if itens:
                    produtos_lista = []
                    for item in itens[:3]:  # Mostrar até 3 produtos
                        nome = item.get('produto_nome', 'N/A')[:20]  # Limitar tamanho
                        qtd = item.get('quantidade', 0)
                        produtos_lista.append(f"{nome}({qtd}x)")
                    produtos_texto = ", ".join(produtos_lista)
                    if len(itens) > 3:
                        produtos_texto += "..."
                
                produtos_label = Label(
                    text=produtos_texto,
                    size_hint_x=0.3,
                    font_size="10sp",
                    halign="left",
                    color=(0.3, 0.3, 0.3, 1)
                )
                row_layout.add_widget(produtos_label)
                
                # Total
                valor_total = pedido.get('valor_total', pedido.get('total', 0))
                total_label = Label(
                    text=f"R$ {valor_total:.2f}",
                    size_hint_x=0.12,
                    font_size="11sp",
                    bold=True,
                    halign="right",
                    color=(0.1, 0.6, 0.1, 1)
                )
                row_layout.add_widget(total_label)
                
                # Botão de ações
                acoes_layout = BoxLayout(size_hint_x=0.08, orientation='horizontal', spacing=1)
                
                btn_editar = Button(
                    text="✏️",
                    size_hint_x=0.5,
                    font_size="10sp",
                    background_color=(0.01, 0.45, 0.89, 1),
                    color=(1, 1, 1, 1)
                )
                btn_editar.bind(on_release=lambda btn, pedido_id=pedido['id']: self._abrir_edicao_venda(pedido_id))
                
                btn_compartilhar = Button(
                    text="📤",
                    size_hint_x=0.5,
                    font_size="10sp",
                    background_color=(0.1, 0.8, 0.1, 1),
                    color=(1, 1, 1, 1)
                )
                btn_compartilhar.bind(on_release=lambda btn, pedido_id=pedido['id']: self.compartilhar_comprovante(pedido_id))
                
                acoes_layout.add_widget(btn_editar)
                acoes_layout.add_widget(btn_compartilhar)
                
                row_layout.add_widget(acoes_layout)
                
                box.add_widget(row_layout)

        except Exception as e:
            logger.error(f"Erro ao atualizar lista de pedidos: {e}")
            self.log(f"Erro ao atualizar lista de pedidos: {e}")

    def _get_pedidos_filtrados(self) -> List[Dict[str, Any]]:
        """Retorna a lista de pedidos filtrados pelo nome do cliente."""
        try:
            if not hasattr(self.ids, 'pedidos_busca_cliente'):
                return self.pedidos
            
            filtro_cliente = self.ids.pedidos_busca_cliente.text.strip().lower()
            
            if not filtro_cliente:
                return self.pedidos
            
            # Filtrar pedidos por nome do cliente
            pedidos_filtrados = []
            for pedido in self.pedidos:
                cliente_nome = pedido.get('cliente_nome', '').lower()
                if filtro_cliente in cliente_nome:
                    pedidos_filtrados.append(pedido)
            
            return pedidos_filtrados
            
        except Exception as e:
            logger.error(f"Erro ao filtrar pedidos: {e}")
            return self.pedidos

    def filtrar_pedidos_por_cliente(self) -> None:
        """Filtra os pedidos baseado no texto digitado no campo de busca."""
        try:
            self._atualizar_lista_pedidos()
        except Exception as e:
            logger.error(f"Erro ao filtrar pedidos por cliente: {e}")

    def limpar_filtro_pedidos(self) -> None:
        """Limpa o filtro de busca de pedidos."""
        try:
            if hasattr(self.ids, 'pedidos_busca_cliente'):
                self.ids.pedidos_busca_cliente.text = ""
            self._atualizar_lista_pedidos()
        except Exception as e:
            logger.error(f"Erro ao limpar filtro de pedidos: {e}")

    def _mostrar_popup_compartilhar(self, pedido_id: int) -> None:
        """Mostra popup perguntando se deseja compartilhar o comprovante."""
        try:
            box = BoxLayout(orientation='vertical', spacing=10, padding=20)
            
            msg = Label(
                text=f"[b]Pedido {pedido_id} finalizado!\\n\\nDeseja compartilhar o comprovante?[/b]",
                markup=True,
                size_hint_y=0.6,
                text_size=(300, None),
                halign='center'
            )
            box.add_widget(msg)
            
            btn_layout = BoxLayout(size_hint_y=0.4, spacing=10)
            
            def criar_comprovante_e_abrir():
                self.compartilhar_comprovante(pedido_id)
                popup.dismiss()
            
            btn_sim = Button(text="Sim, Compartilhar", background_color=(0.1, 0.8, 0.1, 1))
            btn_sim.bind(on_release=lambda x: criar_comprovante_e_abrir())
            
            btn_nao = Button(text="Não", background_color=(0.8, 0.1, 0.1, 1))
            btn_nao.bind(on_release=lambda x: popup.dismiss())
            
            btn_layout.add_widget(btn_sim)
            btn_layout.add_widget(btn_nao)
            
            box.add_widget(btn_layout)
            
            popup = Popup(
                title="Compartilhar Comprovante",
                content=box,
                size_hint=(0.8, 0.4)
            )
            popup.open()
            
        except Exception as e:
            logger.error(f"Erro ao mostrar popup de compartilhamento: {e}")

    def compartilhar_comprovante(self, pedido_id: Optional[int] = None) -> None:
        """Gera e abre o comprovante PNG do pedido."""
        try:
            if pedido_id is None:
                if hasattr(self, 'last_pedido_id') and self.last_pedido_id:
                    pedido_id = self.last_pedido_id
                else:
                    self.log("Nenhum pedido selecionado ou finalizado recentemente.")
                    return
            
            # Obter dados do pedido para gerar o comprovante
            pedido = next((p for p in self.pedidos if p['id'] == pedido_id), None)
            if not pedido:
                self.log(f"Pedido {pedido_id} não encontrado.")
                return
            
            # Obter itens do pedido
            itens = get_itens_pedido(pedido_id)
            cliente_id = pedido.get('cliente_id')
            cliente_nome = pedido.get('cliente_nome', 'N/A')
            cliente_telefone = pedido.get('cliente_telefone', '')
            
            # Montar dicionário do cliente
            cliente = {
                'id': cliente_id,
                'nome': cliente_nome,
                'telefone': cliente_telefone
            }
            
            total = pedido.get('valor_total', pedido.get('total', 0))
            forma_pagamento = pedido.get('forma_pagamento', 'Não informado')
            
            # Gerar comprovante
            from pdf_generator import gerar_comprovante
            png_path = gerar_comprovante(pedido_id, cliente, itens, total, forma_pagamento)
            
            if png_path and os.path.exists(png_path):
                os.startfile(png_path)
                self.log(f"Comprovante do pedido {pedido_id} aberto.")
            else:
                self.log(f"Erro ao gerar comprovante do pedido {pedido_id}.")
        except Exception as e:
            logger.error(f"Erro ao compartilhar comprovante: {e}")
            self.log(f"Erro ao abrir comprovante: {e}")


    def _abrir_edicao_venda(self, pedido_id: int) -> None:
        """
        Abre a aba de venda com o pedido carregado para edição.
        
        Args:
            pedido_id: ID do pedido a editar
        """
        try:
            # Encontrar o pedido
            pedido = next((p for p in self.pedidos if p['id'] == pedido_id), None)
            if not pedido:
                self.log(f"Pedido {pedido_id} não encontrado")
                return
            
            # Buscar e selecionar cliente
            cliente = next(
                (c for c in self.clientes if c['id'] == pedido['cliente_id']),
                None
            )
            if cliente:
                self.cliente_selecionado = cliente
                self.ids.clientes_search.text = cliente['nome']
            
            # Carregar itens do pedido na venda
            self.venda = Venda()
            itens = get_itens_pedido(pedido_id)
            
            for item in itens:
                # Encontrar produto completo
                produto = next(
                    (p for p in self.produtos if p['id'] == item['produto_id']),
                    None
                )
                if produto:
                    self.venda.adicionar_item(produto, item['quantidade'])
            
            # Atualizar interface
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            self.ids.pagamento_spinner.text = pedido.get('forma_pagamento', 'Dinheiro')
            
            # Mudar para aba de venda
            self.ids.tab_panel.switch_to(self.ids.tab_venda)
            
            self.log(f"Pedido #{pedido_id} carregado para edição")
            
        except Exception as e:
            logger.error(f"Erro ao abrir pedido para edição: {e}")
            self.log(f"Erro ao editar pedido: {e}")

    def _limpar_campos_venda(self) -> None:
        """Limpa todos os campos do formulário de venda."""
        try:
            # Limpar campos de busca
            self.ids.clientes_search.text = ""
            self.ids.produtos_search.text = ""
            self.ids.pagamento_spinner.text = "Dinheiro"

            # Limpar quantidade
            self.ids.quantidade_input.text = "1"
            
            # Limpar seleções
            self.cliente_selecionado = None
            self.produto_selecionado = None

            logger.info("Campos de venda limpos")
        except Exception as e:
            logger.error(f"Erro ao limpar campos de venda: {e}")

    def on_tab_venda_enter(self) -> None:
        """Callback chamado quando o usuário entra na aba de venda."""
        try:
            # Recarregar dados para garantir que os produtos mais recentes estão disponíveis
            logger.info("[on_tab_venda_enter] Entrando na aba de venda - recarregando dados...")
            self.reload_data()
            logger.info(f"[on_tab_venda_enter] Produtos carregados: {len(self.produtos)}, Clientes: {len(self.clientes)}")
        except Exception as e:
            logger.error(f"Erro ao entrar na aba de venda: {e}")

    def on_tab_comissao_enter(self) -> None:
        """Callback chamado quando o usuário entra na aba de comissão."""
        try:
            # Carregar automaticamente as datas das vendas
            self.carregar_datas_comissao()
        except Exception as e:
            logger.error(f"Erro ao entrar na aba de comissão: {e}")

    def _limpar_pedido(self) -> None:
        """Limpa completamente o pedido atual e reseta a interface."""
        try:
            # Criar nova venda vazia
            self.venda = Venda()
            
            # Limpar itens visualmente
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            
            # Limpar todos os campos
            self._limpar_campos_venda()
            
            self.log("Pedido limpo com sucesso")
            logger.info("Pedido completo limpo")
            
        except Exception as e:
            logger.error(f"Erro ao limpar pedido: {e}")
            self.log(f"Erro ao limpar pedido: {e}")

    def log(self, msg: str) -> None:
        """
        Atualiza o status log na interface.
        
        Args:
            msg: Mensagem a exibir
        """
        self.status_log = msg
        if hasattr(self, "ids") and self.ids and hasattr(self.ids, "status_label"):
            self.ids.status_label.text = msg

    def _get_texto_do_input(self, input_id: str) -> str:
        """Obtém e limpa texto de um input."""
        try:
            widget = self.ids.get(input_id)
            if widget:
                return widget.text.strip()
            return ""
        except Exception as e:
            logger.error(f"Erro ao obter texto de {input_id}: {e}")
            return ""

    def incrementar_quantidade(self) -> None:
        """Incrementa a quantidade em 1."""
        try:
            qtd_atual = float(self.ids.quantidade_input.text or "0")
            nova_qtd = qtd_atual + 1
            self.ids.quantidade_input.text = str(int(nova_qtd))
        except ValueError:
            self.ids.quantidade_input.text = "1"

    def decrementar_quantidade(self) -> None:
        """Decrementa a quantidade em 1 (mínimo 1)."""
        try:
            qtd_atual = float(self.ids.quantidade_input.text or "0")
            nova_qtd = max(1, qtd_atual - 1)
            self.ids.quantidade_input.text = str(int(nova_qtd))
        except ValueError:
            self.ids.quantidade_input.text = "1"

    # =========================
    # CEP
    # =========================
    def buscar_cep(self) -> None:
        """Busca endereço via ViaCEP utilizando CEP informado."""
        try:
            cep = self._get_texto_do_input("cliente_cep_input").replace("-", "")

            # Validar CEP
            if not cep.isdigit() or len(cep) != CEP_LENGTH:
                self.log(ERROR_CEP_INVALID)
                return

            # Buscar no ViaCEP
            url = CEP_API_URL.format(cep=cep)
            response = requests.get(url, timeout=CEP_TIMEOUT)
            data = response.json()

            if data.get("erro"):
                self.log(ERROR_CEP_NOT_FOUND)
                return

            # Preencher campos
            self.ids.cliente_endereco_input.text = data.get("logradouro", "")
            self.ids.cliente_bairro_input.text = data.get("bairro", "")
            self.ids.cliente_cidade_input.text = data.get("localidade", "")

            self.log(SUCCESS_ENDEREÇO_FILLED)

        except requests.RequestException as e:
            logger.error(f"Erro de requisição CEP: {e}")
            self.log(LOG_CEP_ERROR.format(e))
        except Exception as e:
            logger.error(f"Erro desconhecido ao buscar CEP: {e}")
            self.log(LOG_CEP_ERROR.format(e))

    # =========================
    # CLIENTES
    # =========================
    def add_cliente_ui(self) -> None:
        """Adiciona novo cliente via UI."""
        try:
            nome = self._get_texto_do_input("cliente_nome_input")

            if not nome:
                self.log(ERROR_CLIENT_REQUIRED)
                return

            # Preparar dados do cliente
            cliente_data = {
                "nome": nome,
                "telefone": self._get_texto_do_input("cliente_telefone_input"),
                "cep": self._get_texto_do_input("cliente_cep_input"),
                "endereco": self._get_texto_do_input("cliente_endereco_input"),
                "numero": self._get_texto_do_input("cliente_numero_input"),
                "bairro": self._get_texto_do_input("cliente_bairro_input"),
                "cidade": self._get_texto_do_input("cliente_cidade_input")
            }

            # Se estiver editando cliente existente
            if hasattr(self, 'cliente_em_edicao_id') and self.cliente_em_edicao_id:
                sucesso = editar_cliente_db(
                    self.cliente_em_edicao_id,
                    cliente_data['nome'],
                    cliente_data['telefone'],
                    cliente_data['endereco'],
                    cliente_data['numero'],
                    cliente_data['bairro'],
                    cliente_data['cidade'],
                    cliente_data['cep']
                )
                if sucesso:
                    self.log(f"✅ Cliente '{nome}' atualizado com sucesso!")
                else:
                    self.log(f"❌ Não foi possível atualizar o cliente '{nome}'")

                # voltar para modo novo
                self.cliente_em_edicao_id = None
                if hasattr(self.ids, 'cliente_salvar_button'):
                    self.ids.cliente_salvar_button.text = "Salvar Cliente"
            else:
                add_cliente(cliente_data)
                self.log(SUCCESS_CLIENTE_ADDED.format(nome))
            
            # Limpar campos
            self.ids.cliente_nome_input.text = ""
            self.ids.cliente_telefone_input.text = ""
            self.ids.cliente_cep_input.text = ""
            self.ids.cliente_endereco_input.text = ""
            self.ids.cliente_numero_input.text = ""
            self.ids.cliente_bairro_input.text = ""
            self.ids.cliente_cidade_input.text = ""
            
            self.reload_data()

        except Exception as e:
            logger.error(f"Erro ao adicionar cliente: {e}")
            self.log(LOG_CLIENTE_ERROR.format(e))

    def editar_cliente_ui(self, cliente_id: int) -> None:
        """Carrega cliente nos campos para edição."""
        try:
            cliente = next((c for c in self.clientes if c.get('id') == cliente_id), None)
            if not cliente:
                self.log(f"Cliente {cliente_id} não encontrado")
                return

            self.cliente_em_edicao_id = cliente_id
            self.ids.cliente_nome_input.text = cliente.get('nome', '')
            self.ids.cliente_telefone_input.text = cliente.get('telefone', '')
            self.ids.cliente_cep_input.text = cliente.get('cep', '')
            self.ids.cliente_endereco_input.text = cliente.get('endereco', '')
            self.ids.cliente_numero_input.text = cliente.get('numero', '')
            self.ids.cliente_bairro_input.text = cliente.get('bairro', '')
            self.ids.cliente_cidade_input.text = cliente.get('cidade', '')

            if hasattr(self.ids, 'cliente_salvar_button'):
                self.ids.cliente_salvar_button.text = "Atualizar Cliente"

            self.log(f"Editando cliente: {cliente.get('nome', '')}")

        except Exception as e:
            logger.error(f"Erro ao preparar edição de cliente: {e}")
            self.log(f"Erro ao editar cliente: {e}")

    # =========================
    # VENDEDOR
    # =========================
    def add_vendedor_ui(self) -> None:
        """Cadastra vendedor uma única vez e atualiza os indicadores."""
        try:
            if self.vendedor.get('nome'):
                self.log("Vendedor já cadastrado.")
                return

            nome = self._get_texto_do_input('vendedor_nome_input')
            cpf = self._get_texto_do_input('vendedor_cpf_input')
            rg = self._get_texto_do_input('vendedor_rg_input')
            endereco = self._get_texto_do_input('vendedor_endereco_input')
            bairro = self._get_texto_do_input('vendedor_bairro_input')
            cidade = self._get_texto_do_input('vendedor_cidade_input')

            if not nome:
                self.log('Nome do vendedor é obrigatório.')
                return

            if not cpf:
                self.log('CPF do vendedor é obrigatório.')
                return

            self.vendedor = {
                'nome': nome,
                'cpf': cpf,
                'rg': rg,
                'endereco': endereco,
                'bairro': bairro,
                'cidade': cidade
            }

            # travar campos após cadastro
            for field in [
                'vendedor_nome_input',
                'vendedor_cpf_input',
                'vendedor_rg_input',
                'vendedor_endereco_input',
                'vendedor_bairro_input',
                'vendedor_cidade_input'
            ]:
                if hasattr(self.ids, field):
                    self.ids[field].disabled = True

            self.log(f"Vendedor cadastrado: {nome} ({cpf})")
            self.atualizar_comissao_vendedor()

        except Exception as e:
            logger.error(f"Erro ao cadastrar vendedor: {e}")
            self.log(LOG_PRODUTO_ERROR.format(e))

    def handle_login(self) -> None:
        """Realiza login do vendedor ou redireciona para cadastro."""
        if not self.vendedor.get('nome'):
            self.log("Vendedor não cadastrado. Acesse a aba Login para cadastrar.")
            if hasattr(self.ids, 'tab_panel') and hasattr(self.ids, 'login_tab'):
                self.ids.tab_panel.switch_to(self.ids.login_tab)
            return

        self.log(f"Login efetuado: {self.vendedor.get('nome')}")
        self.atualizar_comissao_vendedor()
        self._atualizar_lista_vendas_comissao()
        if hasattr(self.ids, 'tab_panel') and hasattr(self.ids, 'comissao_tab'):
            self.ids.tab_panel.switch_to(self.ids.comissao_tab)

    def atualizar_comissao_vendedor(self) -> None:
        """Calcula total de vendas e comissão"""
        try:
            # Somar valor_total de todos os pedidos
            total = sum(pedido.get('valor_total', 0) for pedido in self.pedidos)
            self.total_vendas = total

            # Calcular comissão automática baseada em porcentagem
            # (será sobrescrita se usuário digitar porcentagem personalizada)
            if total <= 50000:
                commission = total * 0.05
            else:
                commission = 50000 * 0.05 + (total - 50000) * 0.06

            self.comissao = commission

            if hasattr(self.ids, 'total_vendas_label'):
                self.ids.total_vendas_label.text = f"R$ {self.total_vendas:.2f}"
            if hasattr(self.ids, 'comissao_label'):
                self.ids.comissao_label.text = f"R$ {self.comissao:.2f}"
            
            # Atualizar vendedor na aba comissão
            if hasattr(self.ids, 'vendedor_label') and self.vendedor.get('nome'):
                self.ids.vendedor_label.text = f"Vendedor: {self.vendedor.get('nome', '-')}"

        except Exception as e:
            logger.error(f"Erro ao calcular comissão do vendedor: {e}")
            self.log(LOG_VENDA_ERROR.format(e))

    def carregar_datas_comissao(self) -> None:
        """
        Carrega automaticamente as datas mínima e máxima das vendas 
        quando entra na aba de comissão.
        """
        try:
            if not self.pedidos:
                return

            # Extrair datas dos pedidos
            from datetime import datetime
            
            datas_validas = []
            for pedido in self.pedidos:
                data_str = pedido.get('data_pedido', '')
                if data_str:
                    try:
                        # Tenta converter para validar o formato
                        datetime.strptime(data_str.strip(), "%d/%m/%Y")
                        datas_validas.append(data_str.strip())
                    except ValueError:
                        continue

            if not datas_validas:
                return

            # Ordenar datas
            try:
                datas_ordenadas = sorted(datas_validas, 
                    key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
                
                data_inicio = datas_ordenadas[0]
                data_fim = datas_ordenadas[-1]

                # Preencher os campos se estiverem vazios
                if hasattr(self.ids, 'filtro_data_inicio_input'):
                    if not self.ids.filtro_data_inicio_input.text.strip():
                        self.ids.filtro_data_inicio_input.text = data_inicio

                if hasattr(self.ids, 'filtro_data_fim_input'):
                    if not self.ids.filtro_data_fim_input.text.strip():
                        self.ids.filtro_data_fim_input.text = data_fim

            except Exception as e:
                logger.error(f"Erro ao ordenar datas: {e}")

        except Exception as e:
            logger.error(f"Erro ao carregar datas de comissão: {e}")

    def _atualizar_lista_vendas_comissao(self) -> None:
        """Atualiza a visualização das vendas na aba comissão com data."""
        try:
            if not hasattr(self.ids, 'vendas_comissao_list_box'):
                return
            
            box = self.ids.vendas_comissao_list_box
            box.clear_widgets()

            if not self.pedidos:
                box.add_widget(Label(
                    text="Nenhuma venda até o momento",
                    size_hint_y=None,
                    height="40dp",
                    color=(0.5, 0.5, 0.5, 1)
                ))
                return

            for pedido in self.pedidos:
                # Container da venda
                container = BoxLayout(
                    size_hint_y=None,
                    height=45,
                    padding=5,
                    spacing=5,
                    orientation="horizontal"
                )

                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)
                    rect = Rectangle(size=container.size, pos=container.pos)

                container.bind(
                    pos=lambda inst, value: setattr(rect, 'pos', value),
                    size=lambda inst, value: setattr(rect, 'size', value)
                )

                # Data da venda
                data_pedido = pedido.get('data_pedido', 'N/A')
                # Se a data estiver vazia ou None, mostrar "-"
                if not data_pedido:
                    data_pedido = '-'

                data_label = Label(
                    text=str(data_pedido),
                    size_hint_x=0.2,
                    font_size='11sp',
                    color=(0.1, 0.1, 0.1, 1),
                    halign='center',
                    valign='middle'
                )

                # ID do pedido
                pedido_id_label = Label(
                    text=f"#{pedido.get('id')}",
                    size_hint_x=0.15,
                    font_size='11sp',
                    color=(0.1, 0.1, 0.1, 1),
                    halign='center',
                    valign='middle'
                )

                # Nome do cliente
                cliente_label = Label(
                    text=pedido.get('cliente_nome', 'N/A'),
                    size_hint_x=0.35,
                    font_size='11sp',
                    color=(0.1, 0.1, 0.1, 1),
                    halign='left',
                    valign='middle'
                )
                cliente_label.bind(size=lambda lbl, val: setattr(lbl, 'text_size', (val[0], val[1])))

                # Valor total
                valor_total = pedido.get('valor_total', pedido.get('total', 0))
                valor_label = Label(
                    text=f"R$ {valor_total:.2f}",
                    size_hint_x=0.3,
                    font_size='11sp',
                    bold=True,
                    color=(0.2, 0.8, 0.2, 1),
                    halign='right',
                    valign='middle'
                )

                container.add_widget(data_label)
                container.add_widget(pedido_id_label)
                container.add_widget(cliente_label)
                container.add_widget(valor_label)
                box.add_widget(container)

        except Exception as e:
            logger.error(f"Erro ao atualizar lista de vendas na comissão: {e}")

    def salvar_comissao_vendedor(self) -> None:
        """Salva a comissão (percentual) e os 4 recebimentos programados."""
        try:
            if not self.vendedor.get('nome'):
                self.log("Vendedor não está logado")
                return

            # Validar recebimentos
            recebimentos = []
            for i in range(1, 5):
                data_campo = f"recebimento_{i}_data_input"
                valor_campo = f"recebimento_{i}_valor_input"
                
                if not hasattr(self.ids, data_campo) or not hasattr(self.ids, valor_campo):
                    continue

                data = getattr(self.ids, data_campo).text.strip()
                valor_str = getattr(self.ids, valor_campo).text.strip()

                # Se ambos preenchidos, salvar
                if data and valor_str:
                    try:
                        valor = float(valor_str.replace(",", "."))
                        if valor < 0:
                            self.log(f"❌ Valor do {i}º recebimento não pode ser negativo")
                            return
                        recebimentos.append({
                            "numero": i,
                            "data": data,
                            "valor": valor
                        })
                    except ValueError:
                        self.log(f"❌ Valor inválido no {i}º recebimento")
                        return
                elif data or valor_str:
                    # Se apenas um dos dois foi preenchido
                    self.log(f"❌ Preencha data e valor do {i}º recebimento")
                    return

            # Calcular total dos recebimentos
            total_recebimentos = sum(r['valor'] for r in recebimentos)

            # Atualizar UI com sucesso
            msg = f"✅ Comissão de {self.comissao:.2f} registrada"
            if recebimentos:
                msg += f" com {len(recebimentos)} recebimento(s) programado(s)"
                msg += f" (Total: R$ {total_recebimentos:.2f})"
            
            self.log(msg)

            # Limpar campos após salvar
            self.ids.comissao_percentual_input.text = ""
            for i in range(1, 5):
                getattr(self.ids, f"recebimento_{i}_data_input").text = ""
                getattr(self.ids, f"recebimento_{i}_valor_input").text = ""

        except Exception as e:
            logger.error(f"Erro ao salvar comissão: {e}")
            self.log(f"Erro ao salvar comissão: {e}")

    def calcular_comissao_percentual(self, percentual_texto: str) -> None:
        """
        Calcula comissão baseada em porcentagem sobre total de vendas.
        
        Args:
            percentual_texto: Texto com o valor percentual (ex: "5" para 5%)
        """
        try:
            percentual_texto = (percentual_texto or "").strip()
            
            if not percentual_texto:
                # Se vazio, zerar
                if hasattr(self.ids, 'comissao_calculada_label'):
                    self.ids.comissao_calculada_label.text = "R$ 0.00"
                return

            # Converter percentual
            try:
                percentual = float(percentual_texto.replace(",", "."))
                if percentual < 0:
                    self.log("❌ Porcentagem não pode ser negativa")
                    return
            except ValueError:
                return

            # Calcular comissão: total_vendas * percentual / 100
            comissao_valor = self.total_vendas * percentual / 100

            # Atualizar label
            if hasattr(self.ids, 'comissao_calculada_label'):
                self.ids.comissao_calculada_label.text = f"R$ {comissao_valor:.2f}"
                self.comissao = comissao_valor

        except Exception as e:
            logger.error(f"Erro ao calcular comissão percentual: {e}")

    def abrir_calendario_inicio(self) -> None:
        """Abre calendário popup para selecionar data inicial."""
        self._abrir_calendario('inicio')

    def abrir_calendario_fim(self) -> None:
        """Abre calendário popup para selecionar data final."""
        self._abrir_calendario('fim')

    def _abrir_calendario(self, tipo_data: str) -> None:
        """Abre um popup com calendário para seleção de data.
        
        Args:
            tipo_data: 'inicio' ou 'fim' para indicar qual data está sendo selecionada
        """
        try:
            from datetime import datetime

            # Pegar a data atual
            hoje = datetime.now()
            self.calendario_mes = hoje.month
            self.calendario_ano = hoje.year

            # Criar layout do calendário
            calendario_layout = BoxLayout(orientation='vertical', padding=5, spacing=2, size_hint_y=None, height="200dp")

            # Header com mês/ano e botões de navegação
            header_layout = BoxLayout(size_hint_y=None, height="25dp", spacing=3)
            btn_anterior = Button(text="◀", size_hint_x=0.3, font_size='10sp')
            self.mes_ano_label = Label(text=f"{self._nome_mes(self.calendario_mes)}/{self.calendario_ano}", size_hint_x=0.4, bold=True, font_size='11sp')
            btn_proximo = Button(text="▶", size_hint_x=0.3, font_size='10sp')
            
            # Bind dos botões de navegação
            btn_anterior.bind(on_press=lambda btn: self._navegar_mes(-1, tipo_data))
            btn_proximo.bind(on_press=lambda btn: self._navegar_mes(1, tipo_data))
            
            header_layout.add_widget(btn_anterior)
            header_layout.add_widget(self.mes_ano_label)
            header_layout.add_widget(btn_proximo)
            calendario_layout.add_widget(header_layout)

            # Labels dos dias da semana
            from kivy.uix.gridlayout import GridLayout
            dias_semana_layout = GridLayout(cols=7, size_hint_y=None, height="18dp", spacing=1)
            for dia in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']:
                dias_semana_layout.add_widget(Label(text=dia, color=(0.4, 0.4, 0.4, 1), bold=True, font_size='8sp'))
            calendario_layout.add_widget(dias_semana_layout)

            # Grid com os dias do mês
            self.dias_grid = GridLayout(cols=7, size_hint_y=None, height="110dp", spacing=1)
            self.dias_grid.id = f'dias_grid_{tipo_data}'
            self._atualizar_dias_calendario(tipo_data)
            calendario_layout.add_widget(self.dias_grid)

            # Botão Limpar Filtro
            btn_limpar = Button(text="Limpar", size_hint_y=None, height="25dp", background_color=(0.8, 0.2, 0.2, 1), font_size='10sp')
            btn_limpar.bind(on_press=lambda btn: self._limpar_filtro_periodo())
            calendario_layout.add_widget(btn_limpar)

            # Criar e abrir popup
            self.calendario_popup = Popup(
                title=f"Selecionar Data {'Inicial' if tipo_data == 'inicio' else 'Final'}",
                content=calendario_layout,
                size_hint=(0.6, 0.45)
            )
            self.calendario_popup.open()

        except Exception as e:
            logger.error(f"Erro ao abrir calendário: {e}")
            self.log(f"Erro ao abrir calendário: {e}")

    def _navegar_mes(self, direcao: int, tipo_data: str) -> None:
        """Navega para o mês anterior ou próximo no calendário.
        
        Args:
            direcao: -1 para mês anterior, 1 para próximo
            tipo_data: 'inicio' ou 'fim'
        """
        try:
            self.calendario_mes += direcao
            
            # Ajustar ano se necessário
            if self.calendario_mes > 12:
                self.calendario_mes = 1
                self.calendario_ano += 1
            elif self.calendario_mes < 1:
                self.calendario_mes = 12
                self.calendario_ano -= 1
            
            # Atualizar label do mês/ano
            if hasattr(self, 'mes_ano_label'):
                self.mes_ano_label.text = f"{self._nome_mes(self.calendario_mes)}/{self.calendario_ano}"
            
            # Atualizar dias do calendário
            self._atualizar_dias_calendario(tipo_data)
            
        except Exception as e:
            logger.error(f"Erro ao navegar mês: {e}")

    def _atualizar_dias_calendario(self, tipo_data: str) -> None:
        """Atualiza o grid de dias do calendário para o mês/ano atual."""
        try:
            from datetime import datetime
            
            # Limpar grid atual
            if hasattr(self, 'dias_grid'):
                self.dias_grid.clear_widgets()
            
                # Calcular primeiro dia do mês e número de dias
                primeiro_dia = datetime(self.calendario_ano, self.calendario_mes, 1)
                dia_semana_inicio = primeiro_dia.weekday()  # 0=segunda, 6=domingo
                num_dias = self._num_dias_mes(self.calendario_mes, self.calendario_ano)

                # Adicionar espaços vazios antes do primeiro dia
                for _ in range(dia_semana_inicio):
                    self.dias_grid.add_widget(Label())

                # Adicionar botões para cada dia do mês
                for dia in range(1, num_dias + 1):
                    btn_dia = Button(
                        text=str(dia),
                        size_hint_y=None,
                        height="18dp",
                        background_color=(0.9, 0.9, 0.9, 1),
                        color=(0, 0, 0, 1),
                        font_size='9sp'
                    )
                    btn_dia.bind(on_press=lambda btn, d=dia, m=self.calendario_mes, a=self.calendario_ano, t=tipo_data: self._selecionar_data_calendario(d, m, a, t))
                    self.dias_grid.add_widget(btn_dia)
                    
        except Exception as e:
            logger.error(f"Erro ao atualizar dias do calendário: {e}")

    def _nome_mes(self, mes: int) -> str:
        """Retorna o nome do mês."""
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        return meses[mes - 1] if 1 <= mes <= 12 else ''

    def _num_dias_mes(self, mes: int, ano: int) -> int:
        """Retorna o número de dias em um mês."""
        if mes in [1, 3, 5, 7, 8, 10, 12]:
            return 31
        elif mes in [4, 6, 9, 11]:
            return 30
        elif mes == 2:
            return 29 if (ano % 4 == 0 and ano % 100 != 0) or (ano % 400 == 0) else 28
        return 0

    def _selecionar_data_calendario(self, dia: int, mes: int, ano: int, tipo_data: str) -> None:
        """Processa seleção de data do calendário.
        
        Args:
            dia: Dia selecionado
            mes: Mês
            ano: Ano
            tipo_data: 'inicio' ou 'fim'
        """
        try:
            data_formatada = f"{dia:02d}/{mes:02d}/{ano}"
            
            if tipo_data == 'inicio':
                if hasattr(self.ids, 'filtro_data_inicio_label'):
                    self.ids.filtro_data_inicio_label.text = data_formatada
            else:
                if hasattr(self.ids, 'filtro_data_fim_label'):
                    self.ids.filtro_data_fim_label.text = data_formatada

            # Fechar todos os popups
            try:
                from kivy.app import App
                root_window = App.get_running_app().root_window
                if hasattr(root_window, 'children'):
                    for child in list(root_window.children):
                        if isinstance(child, Popup):
                            child.dismiss()
            except:
                pass

        except Exception as e:
            logger.error(f"Erro ao selecionar data do calendário: {e}")

    def _limpar_filtro_periodo(self) -> None:
        """Limpa os filtros de data."""
        try:
            if hasattr(self.ids, 'filtro_data_inicio_label'):
                self.ids.filtro_data_inicio_label.text = "--/--/----"
            if hasattr(self.ids, 'filtro_data_fim_label'):
                self.ids.filtro_data_fim_label.text = "--/--/----"

            # Fechar todos os popups
            try:
                from kivy.app import App
                root_window = App.get_running_app().root_window
                if hasattr(root_window, 'children'):
                    for child in list(root_window.children):
                        if isinstance(child, Popup):
                            child.dismiss()
            except:
                pass

            # Aplicar filtro (que agora vai mostrar tudo)
            self.filtrar_vendas_por_periodo()

        except Exception as e:
            logger.error(f"Erro ao limpar filtro: {e}")

    def filtrar_vendas_por_periodo(self) -> None:
        """Filtra vendas por período de data e atualiza a lista e totais."""
        try:
            if not hasattr(self.ids, 'filtro_data_inicio_label') or not hasattr(self.ids, 'filtro_data_fim_label'):
                return

            data_inicio_str = self.ids.filtro_data_inicio_label.text.strip()
            data_fim_str = self.ids.filtro_data_fim_label.text.strip()

            # Se ambas vazias, mostrar todas as vendas
            if (not data_inicio_str or data_inicio_str == "--/--/----") and (not data_fim_str or data_fim_str == "--/--/----"):
                self.atualizar_comissao_vendedor()
                self._atualizar_lista_vendas_comissao()
                return

            # Se apenas uma das datas foi preenchida, avisar erro
            if (not data_inicio_str or data_inicio_str == "--/--/----") or (not data_fim_str or data_fim_str == "--/--/----"):
                self.log("❌ Preencha AMBAS as datas (Data Inicial E Data Final)")
                return

            # Converter strings de data
            from datetime import datetime

            def converter_data(data_str):
                """Converte múltiplos formatos de data para objeto datetime"""
                if not data_str:
                    return None
                data_str = data_str.strip()

                # Tenta múltiplos formatos
                formatos = [
                    "%d/%m/%Y",      # 30/03/2026
                    "%d/%m/%y",      # 30/03/26
                    "%Y-%m-%d",      # 2026-03-30
                    "%d-%m-%Y",      # 30-03-2026
                    "%Y-%m-%d %H:%M:%S",  # 2026-03-30 19:37:28 (formato do banco)
                    "%Y-%m-%d %H:%M:%S.%f",  # Com microssegundos
                ]

                for formato in formatos:
                    try:
                        dt = datetime.strptime(data_str, formato)
                        # Para datas com hora, retorna apenas a data (sem hora)
                        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        continue

                return None

            data_inicio = converter_data(data_inicio_str)
            data_fim = converter_data(data_fim_str)

            # Se as datas são inválidas
            if not data_inicio or not data_fim:
                self.log(f"❌ Formato de data inválido. Use DD/MM/AAAA")
                self.log(f"   Data inicial: '{data_inicio_str}' | Data final: '{data_fim_str}'")
                return

            # Verificar se data_inicio é menor ou igual a data_fim
            if data_inicio > data_fim:
                self.log("❌ Data inicial não pode ser maior que data final")
                return

            # Filtrar pedidos dentro do período
            pedidos_filtrados = []
            for pedido in self.pedidos:
                data_pedido_str = pedido.get('data_pedido', '')
                if not data_pedido_str:
                    continue

                data_pedido = converter_data(data_pedido_str)
                if not data_pedido:
                    continue

                # Verificar se está dentro do período (inclusive nos extremos)
                if data_pedido < data_inicio or data_pedido > data_fim:
                    continue

                pedidos_filtrados.append(pedido)

            # Calcular total e comissão apenas com vendas filtradas
            total_filtrado = sum(p.get('valor_total', 0) for p in pedidos_filtrados)

            # Log para debug
            logger.info(f"Filtro aplicado: {len(pedidos_filtrados)} vendas encontradas entre {data_inicio_str} e {data_fim_str}")
            self.log(f"✅ {len(pedidos_filtrados)} venda(s) encontrada(s) no período")

            # Calcular comissão automática baseada em porcentagem
            if total_filtrado <= 50000:
                commission = total_filtrado * 0.05
            else:
                commission = 50000 * 0.05 + (total_filtrado - 50000) * 0.06

            # Atualizar labels com valores filtrados
            if hasattr(self.ids, 'total_vendas_label'):
                self.ids.total_vendas_label.text = f"R$ {total_filtrado:.2f}"
            if hasattr(self.ids, 'comissao_label'):
                self.ids.comissao_label.text = f"R$ {commission:.2f}"

            # Atualizar lista visível com vendas filtradas
            if hasattr(self.ids, 'vendas_comissao_list_box'):
                box = self.ids.vendas_comissao_list_box
                box.clear_widgets()

                if not pedidos_filtrados:
                    box.add_widget(Label(
                        text="Nenhuma venda neste período",
                        size_hint_y=None,
                        height="40dp",
                        color=(0.5, 0.5, 0.5, 1)
                    ))
                else:
                    # Exibir vendas filtradas com o mesmo formato original
                    for pedido in pedidos_filtrados:
                        container = BoxLayout(
                            size_hint_y=None,
                            height=45,
                            padding=5,
                            spacing=5,
                            orientation="horizontal"
                        )

                        container.canvas.before.clear()
                        with container.canvas.before:
                            Color(0.98, 0.98, 1, 1)
                            rect = Rectangle(size=container.size, pos=container.pos)

                        container.bind(
                            pos=lambda inst, value: setattr(rect, 'pos', value),
                            size=lambda inst, value: setattr(rect, 'size', value)
                        )

                        data_pedido = pedido.get('data_pedido', 'N/A')
                        if not data_pedido:
                            data_pedido = '-'

                        data_label = Label(
                            text=str(data_pedido),
                            size_hint_x=0.2,
                            font_size='11sp',
                            color=(0.1, 0.1, 0.1, 1),
                            halign='center',
                            valign='middle'
                        )

                        pedido_id_label = Label(
                            text=f"#{pedido.get('id')}",
                            size_hint_x=0.15,
                            font_size='11sp',
                            color=(0.1, 0.1, 0.1, 1),
                            halign='center',
                            valign='middle'
                        )

                        cliente_label = Label(
                            text=pedido.get('cliente_nome', 'N/A'),
                            size_hint_x=0.35,
                            font_size='11sp',
                            color=(0.1, 0.1, 0.1, 1),
                            halign='left',
                            valign='middle'
                        )
                        cliente_label.bind(size=lambda lbl, val: setattr(lbl, 'text_size', (val[0], val[1])))

                        valor_total = pedido.get('valor_total', pedido.get('total', 0))
                        valor_label = Label(
                            text=f"R$ {valor_total:.2f}",
                            size_hint_x=0.3,
                            font_size='11sp',
                            bold=True,
                            color=(0.2, 0.8, 0.2, 1),
                            halign='right',
                            valign='middle'
                        )

                        container.add_widget(data_label)
                        container.add_widget(pedido_id_label)
                        container.add_widget(cliente_label)
                        container.add_widget(valor_label)
                        box.add_widget(container)

        except Exception as e:
            logger.error(f"Erro ao filtrar vendas por período: {e}")
            self.log(f"❌ Erro: {e}")

    # =========================
    # PRODUTOS
    # =========================
    def calcular_preco_por_variacao(self) -> None:
        """
        Ajusta o campo de preço base conforme as variações de preço.
        Se houver variações configuradas:
            - completa o preço base com o primeiro preço da variação, se estiver vazio
            - desativa edição manual do preço base (para evitar inconsistência)
        Caso contrário, deixa o preço base editável.
        """
        try:
            preco_input = self.ids.produto_preco_input
            variacoes = []

            for i in range(1, 6):
                qtd_text = self.ids[f"produto_qtd{i}_input"].text.strip()
                preco_text = self.ids[f"produto_preco{i}_input"].text.strip()
                if qtd_text and preco_text:
                    try:
                        qtd_val = float(qtd_text.replace(",", "."))
                        preco_val = float(preco_text.replace(",", "."))
                        if qtd_val > 0 and preco_val > 0:
                            variacoes.append((qtd_val, preco_val))
                    except ValueError:
                        continue

            if variacoes:
                # Ordenar por quantidade mínima e usar o menor como preço padrão
                variacoes.sort(key=lambda x: x[0])
                preco_padrao = variacoes[0][1]

                # Se o preço principal estiver vazio ou igual a 0, preencher com preço de variação
                if not preco_input.text.strip() or float(preco_input.text.replace(",", ".")) == 0:
                    preco_input.text = f"{preco_padrao:.2f}" if isinstance(preco_padrao, float) else str(preco_padrao)

                # Desativa preço principal, pois estamos usando tabela de preços variáveis
                preco_input.disabled = True
                preco_input.foreground_color = (0.5, 0.5, 0.5, 1)
                self.log("🧩 Preço base desativado por variações de quantidade")
            else:
                preco_input.disabled = False
                preco_input.foreground_color = (0, 0, 0, 1)

        except Exception as e:
            logger.warning(f"Erro ao calcular preço por variação: {e}")

    def toggle_variacoes(self) -> None:
        """Variações agora estão sempre visíveis - método mantido para compatibilidade."""
        pass

    def add_produto_ui(self) -> None:
        """Adiciona novo produto via UI."""
        try:
            logger.info("=== BOTÃO SALVAR PRODUTO CLICADO ===")
            
            # Verificar se os campos existem
            campos_obrigatorios = ['produto_nome_input', 'produto_preco_input']
            for campo in campos_obrigatorios:
                if not hasattr(self.ids, campo):
                    logger.error(f"Campo {campo} não encontrado!")
                    self.log(f"Erro: Campo {campo} não encontrado")
                    return
            
            nome = self._get_texto_do_input("produto_nome_input")
            
            # Calcular preço baseado em variações se não preenchido
            self.calcular_preco_por_variacao()
            
            preco_str = self._get_texto_do_input("produto_preco_input").replace(",", ".")

            logger.info(f"Nome: '{nome}', Preço: '{preco_str}'")

            # Validações
            if not nome:
                logger.warning("Nome do produto não informado")
                self.log("ERRO: Nome do produto é obrigatório!")
                return

            if not preco_str:
                logger.warning("Preço do produto não informado")
                self.log("ERRO: Preço do produto é obrigatório!")
                return

            # Tentar converter preço
            try:
                preco = float(preco_str)
                if preco <= 0:
                    self.log("ERRO: Preço deve ser maior que zero!")
                    return
            except ValueError:
                self.log("ERRO: Preço inválido!")
                return

            logger.info(f"Produto válido: {nome} - R$ {preco}")
            
            # Verificar se está em modo edição
            if hasattr(self, 'produto_em_edicao_id'):
                self.log(f"Atualizando produto: {nome}...")
            else:
                self.log(f"Cadastrando produto: {nome}...")

            # Preparar dados do produto
            estoque_str = self._get_texto_do_input("produto_estoque_input").replace(",", ".")
            try:
                estoque = float(estoque_str) if estoque_str else 0.0
            except ValueError:
                estoque = 0.0

            produto_data = {
                "nome": nome,
                "preco": preco,
                "codigo_barras": self._get_texto_do_input("produto_codigo_input"),
                "unidade": "UN",
                "estoque": estoque
            }
            
            # Verificar se é edição
            if hasattr(self, 'produto_em_edicao_id'):
                # Modo edição - atualizar produto
                from produtos import editar_produto
                produto_id = self.produto_em_edicao_id
                sucesso = editar_produto(
                    produto_id,
                    nome,
                    preco,
                    produto_data["codigo_barras"],
                    "UN",
                    estoque
                )
                
                if sucesso:
                    logger.info(f"Produto {produto_id} atualizado com sucesso")
                    self.log(f"✅ Produto '{nome}' atualizado com sucesso!")
                    
                    # Limpar variações antigas (usar tabela correta produto_precos)
                    from db import get_conn
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM produto_precos WHERE produto_id = ?", (produto_id,))
                    conn.commit()
                    conn.close()
                else:
                    self.log("Erro ao atualizar o produto!")
                    return
            else:
                # Modo novo - criar produto
                logger.info(f"Salvando produto: {produto_data}")
                produto_id = add_produto(produto_data)
                logger.info(f"Produto salvo com sucesso, ID: {produto_id}")
                self.log(f"✅ Produto '{nome}' cadastrado com sucesso!")
            
            # Salvar variações de preço se informadas (para novo ou edição)
            from produtos import adicionar_preco_variavel
            variacoes_salvas = 0
            
            for i in range(1, 6):  # Até 5 variações
                qtd_str = self._get_texto_do_input(f"produto_qtd{i}_input").replace(",", ".")
                preco_var_str = self._get_texto_do_input(f"produto_preco{i}_input").replace(",", ".")
                
                logger.info(f"Variação {i}: qtd='{qtd_str}', preco='{preco_var_str}'")
                
                if qtd_str and preco_var_str:
                    try:
                        qtd_min = float(qtd_str)
                        preco_var = float(preco_var_str)
                        
                        if qtd_min > 0 and preco_var > 0:
                            sucesso = adicionar_preco_variavel(produto_id, qtd_min, preco_var)
                            if sucesso:
                                variacoes_salvas += 1
                                logger.info(f"Variação {i} salva: {qtd_min}un = R$ {preco_var}")
                    except ValueError:
                        logger.warning(f"Erro ao processar variação {i}")
            
            if variacoes_salvas > 0:
                logger.info(f"{variacoes_salvas} variações de preço salvas")
                self.log(f"✅ {variacoes_salvas} variações de preço salvas!")

                # Desativar preço base no produto (para evitar fallback em vendas)
                try:
                    from produtos import editar_produto
                    editar_produto(
                        produto_id,
                        nome,
                        0.0,
                        produto_data["codigo_barras"],
                        "UN",
                        estoque
                    )
                except Exception as e:
                    logger.warning(f"Não foi possível zerar o preço base após salvar variações: {e}")

            # Limpar campos
            logger.info("Limpando campos de entrada")
            self.ids.produto_nome_input.text = ""
            self.ids.produto_preco_input.text = ""
            self.ids.produto_preco_input.disabled = False
            self.ids.produto_preco_input.foreground_color = (0, 0, 0, 1)
            self.ids.produto_codigo_input.text = ""
            self.ids.produto_estoque_input.text = ""
            
            # Limpar campos de variações
            for i in range(1, 6):
                getattr(self.ids, f"produto_qtd{i}_input").text = ""
                getattr(self.ids, f"produto_preco{i}_input").text = ""
            
            self.ids.produto_busca_input.text = ""
            
            # Reset do botão e remover flag de edição
            if hasattr(self, 'produto_em_edicao_id'):
                delattr(self, 'produto_em_edicao_id')
            self.ids.btn_salvar_produto.text = "Salvar Produto"
            
            # Ocultar variações após salvar
            self.toggle_variacoes()
            
            logger.info("Recarregando dados")
            self.reload_data()
            
            logger.info("Atualizando lista de produtos")
            self.atualizar_lista_produtos()
            
            logger.info("Exibindo mensagem de sucesso")
            self.log("✅ Produto cadastrado com sucesso!")

        except Exception as e:
            logger.error(f"Erro ao adicionar produto: {e}", exc_info=True)
            self.log(f"❌ Erro ao cadastrar produto: {e}")
            
            # Limpar campos
            logger.info("Limpando campos de entrada")
            self.ids.produto_nome_input.text = ""
            self.ids.produto_preco_input.text = ""
            self.ids.produto_preco_input.disabled = False
            self.ids.produto_preco_input.foreground_color = (0, 0, 0, 1)
            self.ids.produto_codigo_input.text = ""
            self.ids.produto_estoque_input.text = ""
            
            # Limpar campos de variações
            for i in range(1, 6):
                getattr(self.ids, f"produto_qtd{i}_input").text = ""
                getattr(self.ids, f"produto_preco{i}_input").text = ""
            
            self.ids.produto_busca_input.text = ""
            
            # Ocultar variações após salvar
            self.toggle_variacoes()
            
            logger.info("Recarregando dados")
            self.reload_data()
            
            logger.info("Atualizando lista de produtos")
            self.atualizar_lista_produtos()
            
            logger.info("Exibindo mensagem de sucesso")
            self.log(SUCCESS_PRODUTO_ADDED.format(nome))

        except Exception as e:
            logger.error(f"Erro ao adicionar produto: {e}", exc_info=True)
            self.log(LOG_PRODUTO_ERROR.format(e))

    def carregar_produtoedicao(self, produto_id: int) -> None:
        """
        Carrega um produto para edição no formulário de cadastro.
        
        Args:
            produto_id: ID do produto a editar
        """
        try:
            # Encontrar o produto
            produto = None
            for p in self.produtos:
                if p['id'] == produto_id:
                    produto = p
                    break
            
            if not produto:
                self.log("Produto não encontrado!")
                return
            
            # Carregar dados nos campos
            self.ids.produto_nome_input.text = produto.get('nome', '')
            self.ids.produto_preco_input.text = str(produto.get('preco', ''))
            self.ids.produto_codigo_input.text = produto.get('codigo_barras', '')
            self.ids.produto_estoque_input.text = str(produto.get('estoque', ''))
            
            # Buscar variações
            from produtos import listar_precos_variaveis
            variacoes = listar_precos_variaveis(produto_id)
            
            # Carregar variações nos campos
            for i in range(1, 6):
                if i <= len(variacoes):
                    var = variacoes[i-1]
                    self.ids[f'produto_qtd{i}_input'].text = str(int(var.get('quantidade_min', '')))
                    self.ids[f'produto_preco{i}_input'].text = str(var.get('preco', ''))
                else:
                    self.ids[f'produto_qtd{i}_input'].text = ""
                    self.ids[f'produto_preco{i}_input'].text = ""

            # Ajustar estado do preço base de acordo com as variações carregadas
            self.calcular_preco_por_variacao()
            
            # Guardar ID para edição
            self.produto_em_edicao_id = produto_id
            
            # Atualizar texto do botão
            self.ids.btn_salvar_produto.text = "Atualizar Produto"
            
            # Fazer scroll para o topo para mostrar o formulário
            try:
                from kivy.clock import Clock
                if hasattr(self.ids, 'tab_produtos'):
                    # Usar Clock para garantir que o scroll aconteça após a UI ser atualizada
                    Clock.schedule_once(lambda dt: setattr(self.ids.tab_produtos, 'scroll_y', 1.0), 0.1)
            except:
                pass
            
            logger.info(f"Produto {produto_id} carregado para edição")
            self.log(f"✏️ Editando: {produto.get('nome')}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar produto para edição: {e}")
            self.log(f"Erro ao carregar produto: {e}")

    def filtrar_produtos(self, texto: str) -> None:
        """
        Filtra produtos baseado no texto de busca.
        
        Args:
            texto: Texto para filtrar (nome ou ID)
        """
        try:
            texto = texto.strip().lower()
            
            if not texto:
                self.atualizar_lista_produtos()
                return
            
            # Filtrar produtos
            produtos_filtrados = [
                p for p in self.produtos
                if (texto in str(p.get('nome', '')).lower() or 
                    texto in str(p.get('id', '')).lower())
            ]
            
            self._exibir_produtos(produtos_filtrados)
            
        except Exception as e:
            logger.error(f"Erro ao filtrar produtos: {e}")

    def atualizar_lista_produtos(self) -> None:
        """Atualiza a visualização completa da lista de produtos."""
        try:
            # Verificar se o widget já foi carregado
            if not hasattr(self.ids, 'produtos_list_box'):
                return
            self._exibir_produtos(self.produtos)
        except Exception as e:
            logger.error(f"Erro ao atualizar lista de produtos: {e}")

    def atualizar_lista_clientes(self) -> None:
        """Atualiza a visualização completa da lista de clientes."""
        try:
            # Verificar se o widget já foi carregado
            if not hasattr(self.ids, 'clientes_list_box'):
                return
            self._exibir_clientes(self.clientes)
        except Exception as e:
            logger.error(f"Erro ao atualizar lista de clientes: {e}")

    def filtrar_clientes(self, termo: str) -> None:
        """Filtra clientes pelo termo (nome/endereço/bairro/cidade)."""
        try:
            termo = (termo or "").strip().lower()
            if not termo:
                self._exibir_clientes(self.clientes)
                return

            resultados = []
            for cliente in self.clientes:
                nome = str(cliente.get('nome', '')).lower()
                endereco = str(cliente.get('endereco', '')).lower()
                numero = str(cliente.get('numero', '')).lower()
                bairro = str(cliente.get('bairro', '')).lower()
                cidade = str(cliente.get('cidade', '')).lower()
                telefone = str(cliente.get('telefone', '')).lower()
                termo_unico = f"{nome} {endereco} {numero} {bairro} {cidade} {telefone}"

                if termo in termo_unico:
                    resultados.append(cliente)

            self._exibir_clientes(resultados)
        except Exception as e:
            logger.error(f"Erro ao filtrar clientes: {e}")


    def salvar_editar_produto(self) -> None:
        """Função obsoleta - use a edição inline diretamente na lista."""
        pass

    def deletar_produto(self) -> None:
        """Função obsoleta - use a edição inline diretamente na lista."""
        pass

    def _exibir_clientes(self, lista_clientes: List[Dict[str, Any]]) -> None:
        """
        Exibe clientes em uma lista.
        
        Args:
            lista_clientes: Lista de clientes a exibir
        """
        try:
            # Proteção: verificar se box existe
            if not hasattr(self.ids, 'clientes_list_box'):
                logger.warning("clientes_list_box ainda não foi carregado")
                return
                
            box = self.ids.clientes_list_box
            box.clear_widgets()

            if not lista_clientes:
                box.add_widget(Label(
                    text="Nenhum cliente encontrado",
                    size_hint_y=None,
                    height="40dp",
                    color=(0.5, 0.5, 0.5, 1)
                ))
                return

            for cliente in lista_clientes:
                # Container com fundo e linha única
                container = BoxLayout(
                    size_hint_y=None,
                    height=50,
                    padding=5,
                    spacing=8,
                    orientation="horizontal"
                )

                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)
                    rect = Rectangle(size=container.size, pos=container.pos)

                container.bind(
                    pos=lambda inst, value: setattr(rect, 'pos', value),
                    size=lambda inst, value: setattr(rect, 'size', value)
                )

                # Botão para editar pelo nome do cliente
                nome_btn = Button(
                    text=str(cliente.get('nome', 'N/A')),
                    size_hint_x=0.25,
                    font_size='12sp',
                    background_color=(0.2, 0.45, 0.8, 0.9),
                    color=(1, 1, 1, 1),
                    text_size=(None, None),
                    halign='center',
                    valign='middle'
                )
                nome_btn.bind(on_release=lambda btn, cid=cliente.get('id'): self.editar_cliente_ui(cid))

                endereco = cliente.get('endereco', '') or ''
                numero = cliente.get('numero', '') or ''
                bairro = cliente.get('bairro', '') or ''
                cidade = cliente.get('cidade', '') or ''

                parts = []
                if endereco:
                    parts.append(endereco)
                if numero:
                    parts.append(f"nº {numero}")
                if bairro:
                    parts.append(bairro)
                if cidade:
                    parts.append(cidade)

                endereco_text = ', '.join(parts) if parts else 'Endereço não informado'

                info_text = (
                    f"ID:{cliente.get('id')} | Tel:{cliente.get('telefone', 'N/A')} | "
                    f"{endereco_text}"
                )

                info_label = Label(
                    text=info_text,
                    size_hint_x=0.75,
                    font_size='11sp',
                    color=(0.1, 0.1, 0.1, 1),
                    halign='left',
                    valign='middle'
                )
                info_label.bind(size=lambda lbl, val: setattr(lbl, 'text_size', (val[0], val[1])))

                container.add_widget(nome_btn)
                container.add_widget(info_label)
                box.add_widget(container)
                
        except Exception as e:
            logger.error(f"Erro ao exibir clientes: {e}")

    def _exibir_produtos(self, lista_produtos: List[Dict[str, Any]]) -> None:
        """
        Exibe produtos em uma lista.
        
        Args:
            lista_produtos: Lista de produtos a exibir
        """
        try:
            # Proteção: verificar se box existe
            if not hasattr(self.ids, 'produtos_list_box'):
                logger.warning("produtos_list_box ainda não foi carregado")
                return
                
            box = self.ids.produtos_list_box
            box.clear_widgets()

            if not lista_produtos:
                box.add_widget(Label(
                    text="Nenhum produto encontrado",
                    size_hint_y=None,
                    height="40dp",
                    color=(0.5, 0.5, 0.5, 1)
                ))
                return

            for produto in lista_produtos:
                # Container com fundo alternado
                container = BoxLayout(
                    size_hint_y=None,
                    height=55,
                    padding=5,
                    spacing=5,
                    orientation="vertical"
                )
                
                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.98, 0.98, 1, 1)  # Azul muito claro
                    rect = Rectangle(size=container.size, pos=container.pos)
                
                container.bind(
                    pos=lambda inst, value: setattr(rect, 'pos', value),
                    size=lambda inst, value: setattr(rect, 'size', value)
                )
                
                # Verificar se produto tem estoque controlado e se está zerado
                estoque = float(produto.get('estoque', 0))
                tem_estoque_controlado = estoque > 0
                sem_estoque = tem_estoque_controlado and estoque <= 0
                
                # Cor do nome baseada no estoque
                cor_nome = (0.8, 0.1, 0.1, 1) if sem_estoque else (0.1, 0.1, 0.1, 1)  # Vermelho se sem estoque
                
                # Buscar variações de preço
                from produtos import listar_precos_variaveis
                variacoes = listar_precos_variaveis(produto.get('id', 0))
                tem_variacoes = len(variacoes) > 0
                
                # Ajustar altura do container baseado nas variações
                altura_container = 75 if tem_variacoes else 55
                
                container.height = altura_container
                
                # Primeira linha: ID + Nome + Preço base + Botão Editar
                linha1 = BoxLayout(size_hint_y=0.4, spacing=5)
                linha1.add_widget(Label(
                    text=f"ID: {produto.get('id')}",
                    size_hint_x=0.15,
                    font_size="11sp",
                    bold=True,
                    color=(0.1, 0.1, 0.1, 1)
                ))
                linha1.add_widget(Label(
                    text=f"{produto.get('nome', 'N/A')}",
                    size_hint_x=0.35,
                    font_size="12sp",
                    bold=True,
                    color=cor_nome
                ))
                linha1.add_widget(Label(
                    text=f"R$ {float(produto.get('preco', 0)):.2f}",
                    size_hint_x=0.2,
                    font_size="12sp",
                    bold=True,
                    color=(0.1, 0.6, 0.1, 1)
                ))
                linha1.add_widget(Label(
                    text=f"Est: {estoque:.1f}" if tem_estoque_controlado else "Est: —",
                    size_hint_x=0.15,
                    font_size="11sp",
                    bold=True,
                    color=(0.8, 0.1, 0.1, 1) if sem_estoque else (0.4, 0.4, 0.4, 1)
                ))
                
                # Botão editar
                btn_editar = Button(
                    text="✏️ Editar",
                    size_hint_x=0.15,
                    font_size="10sp",
                    background_color=(0.01, 0.45, 0.89, 1),
                    color=(1, 1, 1, 1)
                )
                btn_editar.bind(on_release=lambda x, pid=produto.get('id'): self.carregar_produtoedicao(pid))
                linha1.add_widget(btn_editar)
                
                # Segunda linha: Código de barras ou variações
                if tem_variacoes:
                    # Mostrar variações de preço
                    variacoes_text = "Variações: "
                    for i, var in enumerate(variacoes[:3]):  # Mostrar até 3 variações
                        qtd = var.get('quantidade_min', 0)
                        preco = var.get('preco', 0)
                        variacoes_text += f"{int(qtd)}+ R$ {preco:.2f}"
                        if i < len(variacoes[:3]) - 1:
                            variacoes_text += " | "
                    
                    if len(variacoes) > 3:
                        variacoes_text += "..."
                        
                    linha2 = Label(
                        text=variacoes_text,
                        size_hint_y=0.3,
                        font_size="9sp",
                        color=(0.2, 0.5, 0.8, 1),
                        halign="left",
                        text_size=(None, None)
                    )
                else:
                    # Mostrar código de barras
                    codigo = produto.get('codigo_barras', '')
                    linha2_text = f"Código: {codigo}" if codigo else "Código: —"
                    linha2 = Label(
                        text=linha2_text,
                        size_hint_y=0.3,
                        font_size="10sp",
                        color=(0.4, 0.4, 0.4, 1),
                        halign="left"
                    )
                
                # Terceira linha: Código de barras se tem variações
                if tem_variacoes:
                    codigo = produto.get('codigo_barras', '')
                    linha3_text = f"Código: {codigo}" if codigo else "Código: —"
                    linha3 = Label(
                        text=linha3_text,
                        size_hint_y=0.3,
                        font_size="9sp",
                        color=(0.4, 0.4, 0.4, 1),
                        halign="left"
                    )
                    container.add_widget(linha3)
                
                container.add_widget(linha1)
                container.add_widget(linha2)
                box.add_widget(container)
                
        except Exception as e:
            logger.error(f"Erro ao exibir produtos: {e}")

    # =========================
    # ITENS PEDIDO
    # =========================
    def _encontrar_produto_por_label(self, label: str) -> Optional[Dict]:
        """Encontra produto na lista pelo label do spinner."""
        return next(
            (p for p in self.produtos if f"{p['id']} - {p['nome']}" == label),
            None
        )

    def _encontrar_cliente_por_label(self, label: str) -> Optional[Dict]:
        """Encontra cliente na lista pelo label do spinner."""
        return next(
            (c for c in self.clientes if f"{c['id']} - {c['nome']}" == label),
            None
        )

    # =========================
    # BUSCA AUTOMÁTICA (AUTOCOMPLETE)
    # =========================
    def mostrar_sugestoes_cliente(self, textinput, mostrar: bool) -> None:
        """
        Mostra ou esconde as sugestões de clientes.
        
        Args:
            textinput: Campo de texto do cliente
            mostrar: True para mostrar, False para esconder
        """
        try:
            scroll = self.ids.clientes_sugestoes_scroll
            lista = self.ids.clientes_sugestoes_list
            
            if mostrar and textinput.focus:
                # Limpar sugestões anteriores
                lista.clear_widgets()
                
                # Adicionar sugestões
                texto = textinput.text.strip().lower()
                sugestoes = []
                
                if texto:
                    for cliente in self.clientes:
                        nome_lower = str(cliente.get('nome', '')).lower()
                        id_str = str(cliente.get('id', '')).lower()
                        
                        if texto in nome_lower or texto in id_str:
                            sugestoes.append(cliente)
                else:
                    # Mostrar todos se campo vazio
                    sugestoes = self.clientes[:10]  # Limitar a 10 sugestões
                
                for cliente in sugestoes:
                    btn = Button(
                        text=f"{cliente['id']} - {cliente['nome']}",
                        size_hint_y=None,
                        height="40dp",
                        background_color=(0.01, 0.45, 0.89, 1),
                        color=(1, 1, 1, 1),
                        font_size="12sp",
                        halign="left",
                        text_size=(None, None)
                    )
                    btn.bind(on_release=lambda btn, c=cliente: self.selecionar_cliente_sugestao(c, textinput))
                    lista.add_widget(btn)
                
                # Ajustar altura do scroll
                altura_total = len(sugestoes) * 41  # 40dp + 1dp spacing
                altura_max = 200  # Máximo 200dp
                scroll.height = min(altura_total, altura_max) if sugestoes else 0
                scroll.opacity = 1 if sugestoes else 0
            else:
                scroll.height = 0
                scroll.opacity = 0
                
        except Exception as e:
            logger.error(f"Erro ao mostrar sugestões de cliente: {e}")

    def mostrar_sugestoes_produto(self, textinput, mostrar: bool) -> None:
        """
        Mostra ou esconde as sugestões de produtos.
        
        Args:
            textinput: Campo de texto do produto
            mostrar: True para mostrar, False para esconder
        """
        try:
            scroll = self.ids.produtos_sugestoes_scroll
            lista = self.ids.produtos_sugestoes_list
            
            logger.debug(f"[mostrar_sugestoes_produto] mostrar={mostrar}, focus={textinput.focus}, produtos carregados={len(self.produtos)}")
            
            if mostrar and textinput.focus:
                # Limpar sugestões anteriores
                lista.clear_widgets()
                
                # Adicionar sugestões
                texto = textinput.text.strip().lower()
                sugestoes = []
                
                if texto:
                    for produto in self.produtos:
                        nome_lower = str(produto.get('nome', '')).lower()
                        id_str = str(produto.get('id', '')).lower()
                        
                        if texto in nome_lower or texto in id_str:
                            sugestoes.append(produto)
                else:
                    # Mostrar todos se campo vazio
                    sugestoes = self.produtos[:10]  # Limitar a 10 sugestões
                
                logger.debug(f"[mostrar_sugestoes_produto] Encontradas {len(sugestoes)} sugestões")
                
                for produto in sugestoes:
                    # Verificar estoque
                    estoque = float(produto.get('estoque', 0))
                    tem_estoque_controlado = estoque > 0
                    sem_estoque = tem_estoque_controlado and estoque <= 0
                    
                    # Verificar variações de preço
                    from produtos import listar_precos_variaveis
                    variacoes = listar_precos_variaveis(produto.get('id', 0))
                    
                    # Cor do botão baseada no estoque
                    cor_fundo = (0.8, 0.2, 0.2, 1) if sem_estoque else (0.01, 0.45, 0.89, 1)  # Vermelho se sem estoque
                    
                    # Texto do botão com preço base e variações
                    texto_base = f"{produto['id']} - {produto['nome']}"
                    preco_base = float(produto.get('preco', 0))
                    
                    if variacoes:
                        # Mostrar preço base + primeira variação
                        primeira_var = variacoes[0]
                        qtd_var = int(primeira_var.get('quantidade_min', 0))
                        preco_var = primeira_var.get('preco', 0)
                        texto_preco = f"R$ {preco_base:.2f} | {qtd_var}+ R$ {preco_var:.2f}"
                        if len(variacoes) > 1:
                            texto_preco += "..."
                    else:
                        texto_preco = f"R$ {preco_base:.2f}"
                    
                    texto_completo = f"{texto_base}\n{texto_preco}"
                    
                    btn = Button(
                        text=texto_completo,
                        size_hint_y=None,
                        height="50dp",  # Aumentar altura para acomodar 2 linhas
                        background_color=cor_fundo,
                        color=(1, 1, 1, 1),
                        font_size="11sp",
                        halign="left",
                        text_size=(None, None),
                        valign="middle"
                    )
                    btn.bind(on_release=lambda btn, p=produto: self.selecionar_produto_sugestao(p, textinput))
                    lista.add_widget(btn)
                
                # Ajustar altura do scroll (altura dos botões aumentou)
                altura_total = len(sugestoes) * 51  # 50dp + 1dp spacing
                altura_max = 200  # Máximo 200dp
                scroll.height = min(altura_total, altura_max) if sugestoes else 0
                scroll.opacity = 1 if sugestoes else 0
            else:
                scroll.height = 0
                scroll.opacity = 0
                
        except Exception as e:
            logger.error(f"Erro ao mostrar sugestões de produto: {e}", exc_info=True)

    def selecionar_cliente_sugestao(self, cliente: Dict[str, Any], textinput) -> None:
        """
        Seleciona um cliente da lista de sugestões.
        
        Args:
            cliente: Dados do cliente selecionado
            textinput: Campo de texto para atualizar
        """
        try:
            self.cliente_selecionado = cliente
            textinput.text = f"{cliente['id']} - {cliente['nome']}"
            self.log(f"✓ Cliente selecionado: {cliente['nome']} (ID: {cliente['id']})")
            
            # Esconder sugestões
            self.mostrar_sugestoes_cliente(textinput, False)
            
        except Exception as e:
            logger.error(f"Erro ao selecionar cliente: {e}")

    def selecionar_produto_sugestao(self, produto: Dict[str, Any], textinput) -> None:
        """
        Seleciona um produto da lista de sugestões.
        
        Args:
            produto: Dados do produto selecionado
            textinput: Campo de texto para atualizar
        """
        try:
            self.produto_selecionado = produto
            textinput.text = f"{produto['id']} - {produto['nome']}"
            self.log(f"✓ Produto selecionado: {produto['nome']} (ID: {produto['id']})")
            
            # Esconder sugestões
            self.mostrar_sugestoes_produto(textinput, False)
            
        except Exception as e:
            logger.error(f"Erro ao selecionar produto: {e}")

    def buscar_cliente_autocomplete(self, texto: str) -> None:
        """
        Busca cliente em tempo real enquanto digita.
        
        Args:
            texto: Texto digitado no campo de busca
        """
        try:
            texto = texto.strip().lower()
            
            if not texto:
                # Não limpar cliente_selecionado aqui para manter seleção se usuário voltou ao campo
                self.log("Digite o nome ou ID do cliente")
                # Atualizar sugestões
                textinput = self.ids.clientes_search
                self.mostrar_sugestoes_cliente(textinput, textinput.focus)
                return
            
            # Não definir cliente_selecionado automaticamente - só quando clicar nas sugestões
            # Apenas mostrar sugestões filtradas
            textinput = self.ids.clientes_search
            self.mostrar_sugestoes_cliente(textinput, textinput.focus)
            
        except Exception as e:
            logger.error(f"Erro na busca de cliente: {e}")

    def buscar_produto_autocomplete(self, texto: str) -> None:
        """
        Busca produto em tempo real enquanto digita.
        
        Args:
            texto: Texto digitado no campo de busca
        """
        try:
            texto = texto.strip().lower()
            
            if not texto:
                # Não limpar produto_selecionado aqui para manter seleção se usuário voltou ao campo
                self.log("Digite o nome ou ID do produto")
                # Atualizar sugestões
                textinput = self.ids.produtos_search
                self.mostrar_sugestoes_produto(textinput, textinput.focus)
                return
            
            # Não definir produto_selecionado automaticamente - só quando clicar nas sugestões
            # Apenas mostrar sugestões filtradas
            textinput = self.ids.produtos_search
            self.mostrar_sugestoes_produto(textinput, textinput.focus)
            
        except Exception as e:
            logger.error(f"Erro na busca de produto: {e}")

    def add_item_to_pedido(self) -> None:
        """Adiciona item ao pedido."""
        try:
            # Garantir que dados estão carregados
            if not self.produtos:
                logger.warning("Lista de produtos vazia, recarregando dados...")
                self.reload_data()
            
            produto = self.produto_selecionado

            # Se produto não foi explicitamente selecionado pela sugestão, tenta achar pelo texto digitado
            if not produto:
                texto = (self.ids.produtos_search.text or "").strip().lower()
                logger.debug(f"[add_item_to_pedido] Texto digitado: '{texto}', produtos disponíveis: {len(self.produtos)}")
                
                if texto:
                    for p in self.produtos:
                        nome_lower = str(p.get('nome', '')).lower()
                        id_str = str(p.get('id', '')).lower()
                        if texto in nome_lower or texto in id_str:
                            produto = p
                            logger.info(f"[add_item_to_pedido] Produto encontrado pela busca: {p['nome']}")
                            break

            if not produto:
                self.log("❌ Selecione um produto clicando nas sugestões ou digitando nome/ID correto")
                return

            # Converter quantidade
            qtd_str = self.ids.quantidade_input.text.replace(",", ".")
            try:
                qtd = float(qtd_str) if qtd_str else DEFAULT_QUANTITY
            except ValueError:
                qtd = DEFAULT_QUANTITY

            if qtd <= 0:
                qtd = DEFAULT_QUANTITY

            # Tentar adicionar item
            sucesso = self.venda.adicionar_item(produto, qtd)
            
            if not sucesso:
                estoque = float(produto.get('estoque', 0))
                if estoque > 0:
                    self.log(f"❌ Estoque insuficiente! Disponível: {estoque}")
                else:
                    self.log("❌ Erro ao adicionar produto")
                return

            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()

            # Resetar inputs
            self.ids.produtos_search.text = ""
            self.ids.quantidade_input.text = str(int(DEFAULT_QUANTITY))
            self.produto_selecionado = None

            self.log(f"✓ {produto['nome']} adicionado ao pedido")

        except Exception as e:
            logger.error(f"Erro ao adicionar item: {e}")
            self.log(f"Erro ao adicionar item: {e}")

    def atualizar_lista_itens(self) -> None:
        """Atualiza a visualização dos itens no pedido."""
        box = self.ids.itens_box
        box.clear_widgets()

        for i, item in enumerate(self.venda.itens):
            # Container com fundo branco
            container = BoxLayout(
                size_hint_y=None,
                height=50,
                padding=5,
                spacing=5
            )
            container.canvas.before.clear()
            with container.canvas.before:
                Color(1, 1, 1, 1)  # Branco
                rect = Rectangle(size=container.size, pos=container.pos)

            # Garantir atualização do rect ao mover/redimensionar
            container.bind(
                pos=lambda inst, value: setattr(rect, 'pos', value),
                size=lambda inst, value: setattr(rect, 'size', value)
            )

            # TextInput para quantidade (editável)
            quantidade_input = TextInput(
                text=str(int(item['quantidade'])) if item['quantidade'].is_integer() else str(item['quantidade']),
                size_hint_x=0.15,
                size_hint_y=None,
                height=40,
                multiline=False,
                input_filter="float",
                halign="center",
                font_size="14sp"
            )
            quantidade_input.bind(text=lambda inst, value, idx=i: self.alterar_quantidade_item(idx, value))

            # Label para nome do produto
            nome_label = Label(
                text=item['produto_nome'],
                size_hint_x=0.5,
                color=(0.2, 0.2, 0.2, 1),
                font_size="14sp",
                halign="left",
                text_size=(None, None)
            )

            # Label para preço unitário
            preco_label = Label(
                text=f"R$ {item['preco_unitario']:.2f}",
                size_hint_x=0.15,
                color=(0.2, 0.2, 0.2, 1),
                font_size="14sp",
                halign="center"
            )

            # Label para total do item
            total_label = Label(
                text=f"R$ {item['total']:.2f}",
                size_hint_x=0.15,
                color=(0.2, 0.2, 0.2, 1),
                font_size="14sp",
                halign="center",
                bold=True
            )

            # Botão remover
            btn = Button(
                text="❌",
                size_hint_x=0.05,
                size_hint_y=None,
                height=40,
                background_color=(0.9, 0.3, 0.3, 1),
                color=(1, 1, 1, 1),
                font_size="12sp"
            )
            btn.bind(on_release=lambda btn, index=i: self.remover_item(index))

            container.add_widget(quantidade_input)
            container.add_widget(nome_label)
            container.add_widget(preco_label)
            container.add_widget(total_label)
            container.add_widget(btn)
            box.add_widget(container)

    def atualizar_resumo_itens(self) -> None:
        """Atualiza o resumo dos itens adicionados."""
        if hasattr(self.ids, 'itens_resumo'):
            if not self.venda.itens:
                self.ids.itens_resumo.text = "Nenhum item adicionado"
            else:
                resumo = []
                for item in self.venda.itens:
                    resumo.append(f"{item['produto_nome']} ({item['quantidade']}x)")
                self.ids.itens_resumo.text = "Itens: " + ", ".join(resumo)

    def remover_item(self, index: int) -> None:
        """Remove item do pedido pelo índice."""
        self.venda.remover_item(index)
        self.atualizar_lista_itens()
        self.atualizar_resumo_itens()
        self.update_total()

    def alterar_quantidade_item(self, index: int, nova_quantidade: str) -> None:
        """Altera a quantidade de um item no pedido."""
        try:
            qtd = float(nova_quantidade)
            if self.venda.alterar_quantidade(index, qtd):
                self.atualizar_lista_itens()
                self.atualizar_resumo_itens()
                self.update_total()
        except ValueError:
            # Se não for número válido, não faz nada
            pass

    def update_total(self) -> None:
        """Atualiza o total exibido no pedido."""
        self.ids.pedido_total.text = f"TOTAL: R$ {self.venda.total:.2f}"

    # =========================
    # FINALIZAR VENDA
    # =========================
    def finalizar_venda(self) -> None:
        """Finaliza a venda atual e gera comprovante."""
        try:
            # Usar o cliente selecionado pela busca automática
            if not self.cliente_selecionado:
                self.log(ERROR_CLIENT_MUST_CHOOSE)
                return

            cliente = self.cliente_selecionado

            # Configurar venda
            self.venda.definir_cliente(cliente)
            self.venda.definir_pagamento(self.ids.pagamento_spinner.text)

            # Finalizar
            ok, result = self.venda.finalizar_venda()

            if not ok:
                self.log(result)
                return

            # Armazenar ID do último pedido
            if isinstance(result, dict) and 'pedido_id' in result:
                self.last_pedido_id = result['pedido_id']

            # Resetar interface
            self.venda = Venda()
            self.atualizar_lista_itens()
            self.atualizar_resumo_itens()
            self.update_total()
            self._limpar_campos_venda()
            self.carregar_pedidos()
            self.reload_data()

            self.log(SUCCESS_VENDA_FINALIZED)
            
            # Mostrar popup para compartilhar comprovante
            self._mostrar_popup_compartilhar(self.last_pedido_id)

        except Exception as e:
            logger.error(f"Erro ao finalizar venda: {e}")
            self.log(LOG_VENDA_ERROR.format(e))

    # =========================
    # AUTENTICAÇÃO
    # =========================
    def login_com_digital(self) -> None:
        """Permite login rápido via digital (biometria)."""
        try:
            from kivy.uix.gridlayout import GridLayout
            from kivy.uix.scrollview import ScrollView
            
            # Obter lista de usuários com digital habilitada
            usuarios = listar_usuarios_com_biometria()
            
            if not usuarios:
                self.ids.login_erro_label.text = "Nenhum usuário com digital habilitada"
                return
            
            # Criar popup com lista de usuários
            box = BoxLayout(orientation='vertical', padding=10, spacing=10)
            
            label = Label(
                text="Selecione um usuário:",
                size_hint_y=0.1,
                bold=True
            )
            box.add_widget(label)
            
            # ScrollView com lista de usuários
            grid = GridLayout(
                cols=1,
                spacing=5,
                size_hint_y=None,
                height=sum([50 for _ in usuarios]) + (len(usuarios) * 5)
            )
            
            popup = Popup(
                title="Login com Digital",
                content=box,
                size_hint=(0.8, 0.6)
            )
            
            def selecionar_usuario(username):
                """Realiza login com o usuário selecionado."""
                try:
                    # Buscar usuário no banco
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT id, username, email, senha, nome_completo, usa_biometria FROM usuarios WHERE username = ?", (username,))
                    user = cur.fetchone()
                    conn.close()
                    
                    if user:
                        # Montar dicionário do usuário
                        self.usuario_logado = {
                            'id': user[0],
                            'username': user[1],
                            'email': user[2],
                            'senha': user[3],
                            'nome_completo': user[4],
                            'usa_biometria': bool(user[5])
                        }
                        
                        # Atualizar labels
                        self.ids.login_usuario_input.text = ""
                        self.ids.login_senha_input.text = ""
                        self.ids.login_erro_label.text = ""
                        self.ids.vendedor_label.text = f"Vendedor: {self.usuario_logado.get('nome_completo', 'N/A')}"
                        self.log(f"Bem-vindo, {self.usuario_logado['nome_completo']} (Digital)")
                        
                        # Carregar dados
                        self.reload_data()
                        self.carregar_pedidos()
                        
                        # Entrar direto
                        self._mostrar_telas_trabalho()
                        popup.dismiss()
                    else:
                        self.log(f"Erro: usuário {username} não encontrado")
                        
                except Exception as e:
                    logger.error(f"Erro ao fazer login com digital: {e}")
                    self.log(f"Erro ao fazer login: {e}")
            
            # Adicionar botão para cada usuário
            for username in usuarios:
                # Buscar nome completo do usuário
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT nome_completo FROM usuarios WHERE username = ?", (username,))
                result = cur.fetchone()
                conn.close()
                conn.close()
                nome_completo = result[0] if result else username
                
                btn = Button(
                    text=nome_completo,
                    size_hint_y=None,
                    height=50,
                    background_color=(0.2, 0.6, 0.9, 1)
                )
                btn.bind(on_press=lambda x, u=username: selecionar_usuario(u))
                grid.add_widget(btn)
            
            scroll = ScrollView(size_hint=(1, 1))
            scroll.add_widget(grid)
            box.add_widget(scroll)
            
            # Botão Fechar
            btn_fechar = Button(
                text="Fechar",
                size_hint_y=0.1,
                background_color=(0.7, 0.2, 0.2, 1)
            )
            btn_fechar.bind(on_press=lambda x: popup.dismiss())
            box.add_widget(btn_fechar)
            
            popup.open()
            
        except Exception as e:
            logger.error(f"Erro no login com digital: {e}")
            self.ids.login_erro_label.text = f"Erro: {e}"

    def fazer_login(self) -> None:
        """Realiza login do usuário."""
        try:
            username = self._get_texto_do_input("login_usuario_input")
            senha = self._get_texto_do_input("login_senha_input")

            if not username or not senha:
                self.ids.login_erro_label.text = "Usuário e senha obrigatórios"
                return

            # Verificar credenciais
            resultado = verificar_login(username, senha)

            if resultado["sucesso"]:
                # Limpar campos
                self.ids.login_usuario_input.text = ""
                self.ids.login_senha_input.text = ""
                self.ids.login_erro_label.text = ""

                # Armazenar usuário logado
                self.usuario_logado = resultado["usuario"]
                self.ids.vendedor_label.text = f"Vendedor: {self.usuario_logado.get('nome_completo', 'N/A')}"
                self.log(f"Bem-vindo, {resultado['usuario']['nome_completo']}")

                # Carregar dados
                self.reload_data()
                self.carregar_pedidos()

                # Verificar se já tem digital habilitada
                if not self.usuario_logado.get('usa_biometria', False):
                    # Perguntar se quer usar digital
                    self._pergunta_usar_digital()
                else:
                    # Entrar direto
                    self._mostrar_telas_trabalho()

            else:
                self.ids.login_erro_label.text = resultado["mensagem"]

        except Exception as e:
            logger.error(f"Erro ao fazer login: {e}")
            self.ids.login_erro_label.text = f"Erro ao fazer login: {e}"

    def fazer_cadastro(self) -> None:
        """Cadastra novo usuário."""
        try:
            username = self._get_texto_do_input("cadastro_usuario_input")
            email = self._get_texto_do_input("cadastro_email_input")
            nome = self._get_texto_do_input("cadastro_nome_input")
            senha = self._get_texto_do_input("cadastro_senha_input")
            senha_confirma = self._get_texto_do_input("cadastro_senha_confirma_input")
            usa_biometria = self.ids.cadastro_biometria_check.active

            logger.info(f"Cadastro iniciado: username={username}, email={email}, nome={nome}")

            # Validar campos
            if not username or not email or not nome or not senha or not senha_confirma:
                self.ids.cadastro_mensagem_label.text = "Todos os campos são obrigatórios"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.warning("Validação falhou: campos obrigatórios vazios")
                return

            # Validar email básico
            if "@" not in email or "." not in email:
                self.ids.cadastro_mensagem_label.text = "Email inválido"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.warning(f"Email inválido: {email}")
                return

            if senha != senha_confirma:
                self.ids.cadastro_mensagem_label.text = "As senhas não conferem"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.warning("Senhas não conferem")
                return

            if len(senha) < 4:
                self.ids.cadastro_mensagem_label.text = "Senha deve ter no mínimo 4 caracteres"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.warning("Senha muito curta")
                return

            # Verificar se usuário já existe
            if usuario_existe(username):
                self.ids.cadastro_mensagem_label.text = "Este usuário já existe"
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.warning(f"Usuário já existe: {username}")
                return

            # Criar usuário
            logger.info(f"Criando usuário: {username}")
            resultado = add_usuario(username, email, senha, nome, usa_biometria)
            logger.info(f"Resultado da criação: {resultado}")

            if resultado["sucesso"]:
                msg_biometria = " com autenticação por digital habilitada" if usa_biometria else ""
                self.ids.cadastro_mensagem_label.text = f"✓ Conta criada{msg_biometria}! Faça login."
                self.ids.cadastro_mensagem_label.color = (0, 1, 0, 1)
                logger.info(f"Usuário criado com sucesso: {username}")

                # Limpar campos
                self.ids.cadastro_usuario_input.text = ""
                self.ids.cadastro_email_input.text = ""
                self.ids.cadastro_nome_input.text = ""
                self.ids.cadastro_senha_input.text = ""
                self.ids.cadastro_senha_confirma_input.text = ""
                self.ids.cadastro_biometria_check.active = False

                # Voltar para login
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.ir_para_login(), 2)

            else:
                self.ids.cadastro_mensagem_label.text = resultado["mensagem"]
                self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)
                logger.error(f"Erro na criação: {resultado['mensagem']}")

        except Exception as e:
            logger.error(f"Erro ao cadastrar: {e}", exc_info=True)
            self.ids.cadastro_mensagem_label.text = f"Erro ao cadastrar: {e}"
            self.ids.cadastro_mensagem_label.color = (1, 0, 0, 1)

    def ir_para_login(self) -> None:
        """Muda para aba de login."""
        try:
            if hasattr(self.ids, "tab_panel") and hasattr(self.ids, "login_tab"):
                self.ids.tab_panel.switch_to(self.ids.login_tab)
                self.log("Faça login para continuar")
        except Exception as e:
            logger.error(f"Erro ao ir para login: {e}")

    def login_com_digital(self) -> None:
        """Abre diálogo para seleção de usuário e login com digital."""
        try:
            # Buscar usuários com biometria habilitada
            usuarios_biometria = listar_usuarios_com_biometria()

            if not usuarios_biometria:
                self.ids.login_erro_label.text = "Nenhum usuário com digital habilitada"
                return

            # Para simular, vamos permitir a seleção manual ou usar o primeiro
            # Em uma app real, seria integrado com Windows Biometric Framework
            
            # Por ora, vamos criar um simples seletor
            if len(usuarios_biometria) == 1:
                # Se só tem um, faz login direto
                username = usuarios_biometria[0]
                self._autenticar_com_digital(username)
            else:
                # Se tem mais de um, mostra mensagem de seleção
                mensagem = f"Selecione um usuário:\n" + "\n".join(usuarios_biometria)
                self.ids.login_erro_label.text = f"Usuários disponíveis: {', '.join(usuarios_biometria)}"
                logger.info(f"Usuários com biometria: {usuarios_biometria}")

        except Exception as e:
            logger.error(f"Erro ao login com digital: {e}")
            self.ids.login_erro_label.text = f"Erro ao usar digital: {e}"

    def _autenticar_com_digital(self, username: str) -> None:
        """Simula autenticação por digital."""
        try:
            # Em uma app real, aqui verificaríamos a impressão digital do Windows
            # Por enquanto, simulamos apenas preenchendo o usuário
            
            # Verificar credenciais do usuário com biometria
            resultado = verificar_biometria_habilitada(username)
            
            if resultado:
                # Limpar campos de login
                self.ids.login_usuario_input.text = ""
                self.ids.login_senha_input.text = ""
                self.ids.login_erro_label.text = ""

                # Armazenar usuário logado (simulando leitura da digital)
                # Em produção, teríamos o hash da digital armazenado
                from db import get_conn
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT id, username, nome_completo FROM usuarios WHERE username = ?", (username,))
                user = cur.fetchone()
                conn.close()
                
                if user:
                    self.usuario_logado = dict(user)
                    self.log(f"✓ Login com digital bem-sucedido! Bem-vindo, {user['nome_completo']}")

                    # Carregar dados
                    self.reload_data()
                    self.carregar_pedidos()

                    # Mostrar telas de trabalho
                    self._mostrar_telas_trabalho()
                else:
                    self.ids.login_erro_label.text = "Erro ao autenticar com digital"
            else:
                self.ids.login_erro_label.text = "Usuário não tem autenticação por digital habilitada"

        except Exception as e:
            logger.error(f"Erro na autenticação com digital: {e}")
            self.ids.login_erro_label.text = f"Erro na autenticação: {e}"

    def ir_para_cadastro(self) -> None:
        """Muda para aba de cadastro."""
        try:
            if hasattr(self.ids, "tab_panel") and hasattr(self.ids, "cadastro_tab"):
                self.ids.tab_panel.switch_to(self.ids.cadastro_tab)
                self.log("Crie sua conta para começar")
        except Exception as e:
            logger.error(f"Erro ao ir para cadastro: {e}")

    def _pergunta_usar_digital(self) -> None:
        """Mostra popup perguntando se o usuário quer usar autenticação por digital."""
        try:
            from kivy.uix.gridlayout import GridLayout
            
            box = BoxLayout(orientation='vertical', padding=10, spacing=10)
            
            label = Label(
                text="Deseja usar autenticação por digital\npara próximos logins?",
                size_hint_y=0.6
            )
            box.add_widget(label)
            
            botoes_layout = BoxLayout(size_hint_y=0.4, spacing=10)
            
            popup = Popup(
                title="Autenticação Digital",
                content=box,
                size_hint=(0.8, 0.4)
            )
            
            def habilitar_digital():
                """Habilita digital e fecha popup."""
                username = self.usuario_logado.get('username', '')
                resultado = atualizar_biometria_usuario(username, True)
                if resultado['sucesso']:
                    self.log("Autenticação por digital habilitada!")
                    self.usuario_logado['usa_biometria'] = True
                else:
                    self.log(f"Erro: {resultado['mensagem']}")
                popup.dismiss()
                self._mostrar_telas_trabalho()
            
            def nao_habilitar():
                """Não habilita digital e fecha popup."""
                popup.dismiss()
                self._mostrar_telas_trabalho()
            
            btn_sim = Button(text="Sim", background_color=(0.2, 0.7, 0.2, 1))
            btn_sim.bind(on_press=lambda x: habilitar_digital())
            botoes_layout.add_widget(btn_sim)
            
            btn_nao = Button(text="Não", background_color=(0.7, 0.2, 0.2, 1))
            btn_nao.bind(on_press=lambda x: nao_habilitar())
            botoes_layout.add_widget(btn_nao)
            
            box.add_widget(botoes_layout)
            popup.open()
            
        except Exception as e:
            logger.error(f"Erro ao mostrar popup de digital: {e}")
            self._mostrar_telas_trabalho()

    def abrir_perfil(self) -> None:
        """Abre a aba de perfil oculta."""
        if not self.usuario_logado:
            return
        
        try:
            # Preencher campos com dados atuais
            self.ids.perfil_usuario_input.text = self.usuario_logado.get('username', '')
            self.ids.perfil_nome_input.text = self.usuario_logado.get('nome_completo', '')
            self.ids.perfil_email_input.text = self.usuario_logado.get('email', '')
            self.ids.perfil_digital_check.active = self.usuario_logado.get('usa_biometria', False)
            
            # Campos opcionais
            self.ids.perfil_cpf_input.text = self.usuario_logado.get('cpf', '')
            self.ids.perfil_rg_input.text = self.usuario_logado.get('rg', '')
            self.ids.perfil_cep_input.text = self.usuario_logado.get('cep', '')
            self.ids.perfil_endereco_input.text = self.usuario_logado.get('endereco', '')
            self.ids.perfil_numero_input.text = self.usuario_logado.get('numero', '')
            self.ids.perfil_complemento_input.text = self.usuario_logado.get('complemento', '')
            self.ids.perfil_bairro_input.text = self.usuario_logado.get('bairro', '')
            self.ids.perfil_cidade_input.text = self.usuario_logado.get('cidade', '')
            self.ids.perfil_estado_input.text = self.usuario_logado.get('estado', '')
            self.ids.perfil_foto_input.text = self.usuario_logado.get('foto', '')
            
            # Habilitar e mostrar aba de perfil
            self.ids.tab_perfil.disabled = False
            self.ids.tab_panel.switch_to(self.ids.tab_perfil)
            
            logger.info("Aba de perfil aberta")
            
        except Exception as e:
            logger.error(f"Erro ao abrir perfil: {e}")
            self.log(f"Erro ao abrir perfil: {e}")

    def salvar_perfil(self) -> None:
        """Salva as alterações do perfil do usuário."""
        if not self.usuario_logado:
            return
        
        try:
            # Obter novos valores
            nome = self._get_texto_do_input("perfil_nome_input").strip()
            email = self._get_texto_do_input("perfil_email_input").strip()
            usa_biometria = self.ids.perfil_digital_check.active
            
            # Campos opcionais
            cpf = self._get_texto_do_input("perfil_cpf_input").strip()
            rg = self._get_texto_do_input("perfil_rg_input").strip()
            cep = self._get_texto_do_input("perfil_cep_input").strip()
            endereco = self._get_texto_do_input("perfil_endereco_input").strip()
            numero = self._get_texto_do_input("perfil_numero_input").strip()
            complemento = self._get_texto_do_input("perfil_complemento_input").strip()
            bairro = self._get_texto_do_input("perfil_bairro_input").strip()
            cidade = self._get_texto_do_input("perfil_cidade_input").strip()
            estado = self._get_texto_do_input("perfil_estado_input").strip()
            foto = self._get_texto_do_input("perfil_foto_input").strip()
            
            # Validações
            if not nome:
                self.log("Nome completo é obrigatório")
                return
            
            if not email:
                self.log("Email é obrigatório")
                return
            
            # Verificar se email já existe para outro usuário
            usuario_id_atual = self.usuario_logado.get('id', 0)
            if email != self.usuario_logado.get('email', ''):
                from db import usuario_existe_por_email
                if usuario_existe_por_email(email, self.usuario_logado.get('username', '')):
                    self.log("Este email já está sendo usado por outro usuário")
                    return
            
            # Atualizar no banco de dados
            from db import atualizar_usuario
            resultado = atualizar_usuario(
                usuario_id=usuario_id_atual,
                nome_completo=nome,
                email=email,
                usa_biometria=usa_biometria,
                cpf=cpf,
                rg=rg,
                cep=cep,
                endereco=endereco,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                cidade=cidade,
                estado=estado,
                foto=foto
            )
            
            if resultado["sucesso"]:
                # Atualizar dados em memória
                self.usuario_logado['nome_completo'] = nome
                self.usuario_logado['email'] = email
                self.usuario_logado['usa_biometria'] = usa_biometria
                self.usuario_logado['cpf'] = cpf
                self.usuario_logado['rg'] = rg
                self.usuario_logado['cep'] = cep
                self.usuario_logado['endereco'] = endereco
                self.usuario_logado['numero'] = numero
                self.usuario_logado['complemento'] = complemento
                self.usuario_logado['bairro'] = bairro
                self.usuario_logado['cidade'] = cidade
                self.usuario_logado['estado'] = estado
                self.usuario_logado['foto'] = foto
                
                # Atualizar label do vendedor na comissão
                self.ids.vendedor_label.text = f"Vendedor: {nome}"
                
                self.log("Perfil atualizado com sucesso!")
                logger.info(f"Perfil do usuário '{self.usuario_logado.get('username', '')}' atualizado")
            else:
                self.log(f"Erro ao salvar perfil: {resultado['mensagem']}")
                
        except Exception as e:
            logger.error(f"Erro ao salvar perfil: {e}")
            self.log(f"Erro ao salvar perfil: {e}")

    def buscar_cep_perfil(self) -> None:
        """Busca dados do endereço via CEP para o perfil."""
        try:
            cep = self._get_texto_do_input("perfil_cep_input").strip()
            
            if not cep:
                self.log("Digite um CEP válido")
                return
            
            # Remover caracteres não numéricos
            cep = ''.join(filter(str.isdigit, cep))
            
            if len(cep) != 8:
                self.log("CEP deve ter 8 dígitos")
                return
            
            # Fazer requisição para ViaCEP
            import requests
            url = f"https://viacep.com.br/ws/{cep}/json/"
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get('erro'):
                    self.log("CEP não encontrado")
                    return
                
                # Preencher campos automaticamente
                if data.get('logradouro'):
                    self.ids.perfil_endereco_input.text = data['logradouro']
                if data.get('bairro'):
                    self.ids.perfil_bairro_input.text = data['bairro']
                if data.get('localidade'):
                    self.ids.perfil_cidade_input.text = data['localidade']
                if data.get('uf'):
                    self.ids.perfil_estado_input.text = data['uf']
                
                self.log("Endereço preenchido automaticamente")
                
            except requests.RequestException as e:
                logger.error(f"Erro na requisição ViaCEP: {e}")
                self.log("Erro ao buscar CEP. Verifique sua conexão")
                
        except Exception as e:
            logger.error(f"Erro ao buscar CEP: {e}")
            self.log(f"Erro ao buscar CEP: {e}")

    def selecionar_foto_perfil(self) -> None:
        """Abre diálogo para seleção de foto do perfil."""
        try:
            from kivy.uix.filechooser import FileChooserListView
            from kivy.uix.popup import Popup
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.button import Button
            import os
            
            # Layout do popup
            layout = BoxLayout(orientation='vertical')
            
            # FileChooser
            filechooser = FileChooserListView(
                path=os.path.expanduser("~"),
                filters=['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp']
            )
            
            # Botões
            btn_layout = BoxLayout(size_hint_y=None, height=50)
            btn_cancelar = Button(text='Cancelar')
            btn_selecionar = Button(text='Selecionar')
            
            btn_layout.add_widget(btn_cancelar)
            btn_layout.add_widget(btn_selecionar)
            
            layout.add_widget(filechooser)
            layout.add_widget(btn_layout)
            
            # Popup
            popup = Popup(
                title='Selecionar Foto',
                content=layout,
                size_hint=(0.9, 0.9)
            )
            
            def on_cancelar(instance):
                popup.dismiss()
            
            def on_selecionar(instance):
                if filechooser.selection:
                    caminho_foto = filechooser.selection[0]
                    self.ids.perfil_foto_input.text = caminho_foto
                    self.log("Foto selecionada com sucesso")
                else:
                    self.log("Nenhuma foto selecionada")
                popup.dismiss()
            
            btn_cancelar.bind(on_press=on_cancelar)
            btn_selecionar.bind(on_press=on_selecionar)
            
            popup.open()
            
        except Exception as e:
            logger.error(f"Erro ao abrir seletor de foto: {e}")
            self.log(f"Erro ao abrir seletor de foto: {e}")

    def fazer_logout(self) -> None:
        """Realiza logout do usuário."""
        try:
            self.usuario_logado = None
            self.ids.vendedor_label.text = "Vendedor: -"
            self.log("Logout realizado com sucesso")
            self._mostrar_telas_login()
            
        except Exception as e:
            logger.error(f"Erro ao fazer logout: {e}")
            self.log(f"Erro ao fazer logout: {e}")

    def fechar_perfil(self) -> None:
        """Fecha a aba de perfil e volta para a aba anterior."""
        try:
            # Ocultar aba de perfil
            self.ids.tab_perfil.disabled = True
            
            # Voltar para aba de clientes (ou primeira disponível)
            if hasattr(self.ids, "tab_clientes") and not self.ids.tab_clientes.disabled:
                self.ids.tab_panel.switch_to(self.ids.tab_clientes)
            elif hasattr(self.ids, "tab_produtos") and not self.ids.tab_produtos.disabled:
                self.ids.tab_panel.switch_to(self.ids.tab_produtos)
            elif hasattr(self.ids, "tab_venda") and not self.ids.tab_venda.disabled:
                self.ids.tab_panel.switch_to(self.ids.tab_venda)
            
            logger.info("Aba de perfil fechada")
            
        except Exception as e:
            logger.error(f"Erro ao fechar perfil: {e}")
            self.log(f"Erro ao fechar perfil: {e}")

    def _mostrar_telas_login(self) -> None:
        """Move as telas de login/cadastro para o início e desativa as telas de trabalho."""
        try:
            tabs = self.ids.tab_panel
            
            # Habilitar abas de login/cadastro
            self.ids.login_tab.disabled = False
            self.ids.cadastro_tab.disabled = False
            
            # Desabilitar abas de trabalho
            self._desabilitar_abas_trabalho()
            
            # Mover para aba de login
            self.ids.tab_panel.switch_to(self.ids.login_tab)
            
            logger.info("Telas de login/cadastro reativadas")
        except Exception as e:
            logger.error(f"Erro ao mostrar telas login: {e}")

    def _mostrar_telas_trabalho(self) -> None:
        """Move as telas de login/cadastro para o final e ativa as telas de trabalho."""
        try:
            tab_panel = self.ids.tab_panel
            
            # Ocultar abas de login/cadastro
            self.ids.login_tab.disabled = True
            self.ids.cadastro_tab.disabled = True
            
            # Habilitar abas de trabalho
            self._habilitar_abas_trabalho()
            
            # Mudar para aba de Clientes como primeira tela após login
            if hasattr(self.ids, "tab_clientes"):
                self.ids.tab_panel.switch_to(self.ids.tab_clientes)

        except Exception as e:
            logger.error(f"Erro ao mostrar telas de trabalho: {e}")

    def _desabilitar_abas_trabalho(self) -> None:
        """Desabilita todas as abas de trabalho (apenas Login e Cadastro habilitadas)."""
        try:
            tab_panel = self.ids.tab_panel
            
            # Mostrar abas de login/cadastro
            self.ids.login_tab.disabled = False
            self.ids.cadastro_tab.disabled = False
            
            # Nomes das abas a desabilitar
            abas_desabilitar = [
                "tab_clientes",
                "tab_produtos",
                "tab_venda", 
                "comissao_tab",
                "tab_pedidos",
                "tab_inventario",
                "tab_perfil"
            ]
            
            # Desabilitar abas
            for aba_id in abas_desabilitar:
                if hasattr(self.ids, aba_id):
                    aba = self.ids[aba_id]
                    aba.disabled = True
                    logger.debug(f"Aba {aba_id} desabilitada")
                    
        except Exception as e:
            logger.error(f"Erro ao desabilitar abas: {e}")

    def _habilitar_abas_trabalho(self) -> None:
        """Habilita todas as abas de trabalho após login bem-sucedido."""
        try:
            tab_panel = self.ids.tab_panel
            
            # Nomes das abas a habilitar
            abas_habilitar = [
                "tab_clientes",
                "tab_produtos",
                "tab_venda",
                "comissao_tab",
                "tab_pedidos",
                "tab_inventario"
            ]
            
            # Habilitar abas
            for aba_id in abas_habilitar:
                if hasattr(self.ids, aba_id):
                    aba = self.ids[aba_id]
                    aba.disabled = False
                    logger.debug(f"Aba {aba_id} habilitada")
                    
        except Exception as e:
            logger.error(f"Erro ao habilitar abas: {e}")

    def atualizar_inventario(self) -> None:
        """Atualiza o inventário completo (estoque atual e produtos mais vendidos)."""
        try:
            logger.info("Atualizando inventário...")
            
            # Verificar se os widgets já foram carregados
            if hasattr(self.ids, 'inventario_list_box'):
                # Atualizar estoque atual
                self._exibir_inventario()
            else:
                logger.warning("Widget inventario_list_box ainda não carregado")
            
            if hasattr(self.ids, 'mais_vendidos_list_box'):
                # Atualizar produtos mais vendidos
                self._exibir_mais_vendidos()
            else:
                logger.warning("Widget mais_vendidos_list_box ainda não carregado")
            
            self.log("Inventário atualizado com sucesso!")
            logger.info("Inventário atualizado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar inventário: {e}")
            self.log(f"Erro ao atualizar inventário: {e}")

    def _exibir_inventario(self) -> None:
        """Exibe o inventário atual com controle de estoque."""
        try:
            # Verificar se o widget já foi carregado
            if not hasattr(self.ids, 'inventario_list_box'):
                logger.warning("inventario_list_box ainda não foi carregado")
                return
                
            box = self.ids.inventario_list_box
            box.clear_widgets()
            
            # Obter todos os produtos
            produtos = list_produtos()
            logger.info(f"Exibindo inventário com {len(produtos)} produtos")
            
            if not produtos:
                # Mensagem quando não há produtos
                label = Label(
                    text="[b]Nenhum produto cadastrado[/b]",
                    markup=True,
                    size_hint_y=None,
                    height="40dp",
                    color=(0.5, 0.5, 0.5, 1),
                    font_size="14sp",
                    halign="center"
                )
                box.add_widget(label)
                return
            
            # Cabeçalho
            header = BoxLayout(
                size_hint_y=None,
                height="35dp",
                spacing=5,
                padding=[5, 0]
            )
            
            header.add_widget(Label(
                text="[b]Produto[/b]",
                markup=True,
                size_hint_x=0.4,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True
            ))
            
            header.add_widget(Label(
                text="[b]Estoque[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            header.add_widget(Label(
                text="[b]Preço[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            header.add_widget(Label(
                text="[b]Valor Total[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            box.add_widget(header)
            
            # Linha separadora simples
            separator = Label(text="-" * 50, size_hint_y=None, height="20dp", color=(0.8, 0.8, 0.8, 1), halign="center")
            box.add_widget(separator)
            
            # Exibir produtos
            total_valor_estoque = 0
            for produto in produtos:
                # Determinar cor do nome (vermelho se estoque zero)
                estoque = produto.get('estoque', 0)
                nome_cor = (1, 0, 0, 1) if estoque == 0 else (0, 0, 0, 1)  # Vermelho se sem estoque
                
                # Calcular valor total do estoque
                preco = produto.get('preco', 0)
                valor_total = estoque * preco
                total_valor_estoque += valor_total
                
                # Container do produto
                item_box = BoxLayout(
                    size_hint_y=None,
                    height="30dp",
                    spacing=5,
                    padding=[5, 0]
                )
                
                # Nome do produto
                item_box.add_widget(Label(
                    text=produto.get('nome', ''),
                    size_hint_x=0.4,
                    color=nome_cor,
                    font_size="11sp",
                    bold=estoque == 0  # Negrito se sem estoque
                ))
                
                # Estoque
                item_box.add_widget(Label(
                    text=str(estoque),
                    size_hint_x=0.2,
                    color=(0, 0, 0, 1),
                    font_size="11sp",
                    halign="center"
                ))
                
                # Preço
                item_box.add_widget(Label(
                    text=f"R$ {preco:.2f}",
                    size_hint_x=0.2,
                    color=(0, 0, 0, 1),
                    font_size="11sp",
                    halign="center"
                ))
                
                # Valor total
                item_box.add_widget(Label(
                    text=f"R$ {valor_total:.2f}",
                    size_hint_x=0.2,
                    color=(0, 0, 0, 1),
                    font_size="11sp",
                    halign="center"
                ))
                
                box.add_widget(item_box)
            
            # Total do estoque
            if produtos:
                total_box = BoxLayout(
                    size_hint_y=None,
                    height="35dp",
                    spacing=5,
                    padding=[5, 5]
                )
                
                total_box.add_widget(Label(
                    text="[b]TOTAL DO ESTOQUE:[/b]",
                    markup=True,
                    size_hint_x=0.8,
                    color=(0, 0.5, 0, 1),
                    font_size="13sp",
                    bold=True
                ))
                
                total_box.add_widget(Label(
                    text=f"[b]R$ {total_valor_estoque:.2f}[/b]",
                    markup=True,
                    size_hint_x=0.2,
                    color=(0, 0.5, 0, 1),
                    font_size="13sp",
                    bold=True,
                    halign="right"
                ))
                
                box.add_widget(total_box)
                
        except Exception as e:
            logger.error(f"Erro ao exibir inventário: {e}")

    def _exibir_mais_vendidos(self) -> None:
        """Exibe os produtos mais vendidos por valor total."""
        try:
            # Verificar se o widget já foi carregado
            if not hasattr(self.ids, 'mais_vendidos_list_box'):
                logger.warning("mais_vendidos_list_box ainda não foi carregado")
                return
                
            box = self.ids.mais_vendidos_list_box
            box.clear_widgets()
            
            # Obter estatísticas de vendas por produto
            vendas_por_produto = self._calcular_vendas_por_produto()
            
            if not vendas_por_produto:
                # Mensagem quando não há vendas
                label = Label(
                    text="[b]Nenhuma venda registrada[/b]",
                    markup=True,
                    size_hint_y=None,
                    height="40dp",
                    color=(0.5, 0.5, 0.5, 1),
                    font_size="14sp",
                    halign="center"
                )
                box.add_widget(label)
                return
            
            # Ordenar por valor total vendido (decrescente)
            vendas_ordenadas = sorted(
                vendas_por_produto.items(), 
                key=lambda x: x[1]['valor_total'], 
                reverse=True
            )
            
            # Cabeçalho
            header = BoxLayout(
                size_hint_y=None,
                height="35dp",
                spacing=5,
                padding=[5, 0]
            )
            
            header.add_widget(Label(
                text="[b]Produto[/b]",
                markup=True,
                size_hint_x=0.4,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True
            ))
            
            header.add_widget(Label(
                text="[b]Qtd Vendida[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            header.add_widget(Label(
                text="[b]Valor Total[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            header.add_widget(Label(
                text="[b]Lucro %[/b]",
                markup=True,
                size_hint_x=0.2,
                color=(0, 0, 0, 1),
                font_size="12sp",
                bold=True,
                halign="center"
            ))
            
            box.add_widget(header)
            
            # Linha separadora simples
            separator = Label(text="-" * 50, size_hint_y=None, height="20dp", color=(0.8, 0.8, 0.8, 1), halign="center")
            box.add_widget(separator)
            
            # Exibir produtos mais vendidos (top 10)
            total_vendas = sum(venda['valor_total'] for venda in vendas_por_produto.values())
            
            for i, (produto_id, dados) in enumerate(vendas_ordenadas[:10]):  # Top 10
                # Calcular percentual de lucro
                percentual = (dados['valor_total'] / total_vendas * 100) if total_vendas > 0 else 0
                
                # Container do produto
                item_box = BoxLayout(
                    size_hint_y=None,
                    height="30dp",
                    spacing=5,
                    padding=[5, 0]
                )
                
                # Nome do produto
                item_box.add_widget(Label(
                    text=dados['nome'],
                    size_hint_x=0.4,
                    color=(0, 0, 0, 1),
                    font_size="11sp"
                ))
                
                # Quantidade vendida
                item_box.add_widget(Label(
                    text=str(dados['quantidade_total']),
                    size_hint_x=0.2,
                    color=(0, 0, 0, 1),
                    font_size="11sp",
                    halign="center"
                ))
                
                # Valor total
                item_box.add_widget(Label(
                    text=f"R$ {dados['valor_total']:.2f}",
                    size_hint_x=0.2,
                    color=(0, 0, 0, 1),
                    font_size="11sp",
                    halign="center"
                ))
                
                # Percentual de lucro
                item_box.add_widget(Label(
                    text=f"{percentual:.1f}%",
                    size_hint_x=0.2,
                    color=(0, 0.5, 0, 1) if percentual > 20 else (0.7, 0.3, 0, 1),
                    font_size="11sp",
                    halign="center",
                    bold=percentual > 20
                ))
                
                box.add_widget(item_box)
                
        except Exception as e:
            logger.error(f"Erro ao exibir produtos mais vendidos: {e}")

    def _calcular_vendas_por_produto(self) -> Dict[str, Dict[str, Any]]:
        """Calcula estatísticas de vendas por produto."""
        try:
            vendas_por_produto = {}
            
            # Obter mapeamento de produtos para nomes
            produtos_map = {str(p['id']): p['nome'] for p in list_produtos()}
            
            # Obter todas as vendas (pedidos finalizados)
            vendas = list_pedidos("finalizado")
            
            for venda in vendas:
                itens = get_itens_pedido(venda.get('id', 0))
                for item in itens:
                    produto_id = str(item.get('produto_id', ''))
                    quantidade = item.get('quantidade', 0)
                    preco_unitario = item.get('preco_unitario', 0)
                    valor_total_item = quantidade * preco_unitario
                    
                    if produto_id not in vendas_por_produto:
                        # Obter nome do produto
                        nome_produto = produtos_map.get(produto_id, f'Produto {produto_id}')
                        
                        vendas_por_produto[produto_id] = {
                            'nome': nome_produto,
                            'quantidade_total': 0,
                            'valor_total': 0
                        }
                    
                    vendas_por_produto[produto_id]['quantidade_total'] += quantidade
                    vendas_por_produto[produto_id]['valor_total'] += valor_total_item
            
            return vendas_por_produto
            
        except Exception as e:
            logger.error(f"Erro ao calcular vendas por produto: {e}")
            return {}


def verificar_single_instance() -> bool:
    """
    Verifica se a aplicação já está rodando.
    Usa um socket para garantir apenas uma instância.
    
    Returns:
        bool: True se é a primeira instância, False se já existe outra
    """
    try:
        # Criar socket para lock
        socket_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Tentar conectar a um socket local (significa que outra instância está rodando)
        socket_lock.bind(("127.0.0.1", 54321))
        
        logger.info("✓ Primeira instância autorizada")
        return True
        
    except OSError:
        logger.warning("✗ Aplicação já está em execução!")
        return False
    except Exception as e:
        logger.error(f"Erro ao verificar instância: {e}")
        return True  # Considerar como primeira instância em caso de erro


class VendasApp(App):
    """Aplicação principal de controle de vendas."""

    def build(self):
        """
        Constrói a interface da aplicação.
        
        Carrega o arquivo app.kv e retorna o widget raiz.
        """
        try:
            print("Iniciando aplicação...")
            
            # Inicializar banco de dados
            try:
                init_db()
                print("Banco de dados OK")
            except Exception as e:
                print(f"Erro DB: {e}")
                return None
            
            # Configurações da janela
            from kivy.core.window import Window
            from kivy.metrics import Metrics
            from kivy.utils import platform
            
            # Detectar plataforma
            is_mobile = platform in ['android', 'ios']
            print(f"Plataforma detectada: {platform} (móvel: {is_mobile})")
            
            # Obter dimensões da tela a partir do monitor real (evitar valores estáticos)
            try:
                screen_width, screen_height = Window.system_size
            except Exception:
                # fallback caso system_size não funcione em alguns backends
                screen_width = Metrics.dpi * 15.6  # Aproximadamente 1920px em 96dpi
                screen_height = Metrics.dpi * 8.7   # Aproximadamente 1080px em 96dpi

            print(f"Resolução detectada: {screen_width}x{screen_height}")
            
            if is_mobile:
                # Configurações para dispositivos móveis
                Window.fullscreen = 'auto'  # Modo tela cheia automático
                Window.show_cursor = False  # Esconder cursor em touch screens
                print("Modo móvel ativado - tela cheia")
            else:
                # Configurações para PC/desktop - MAXIMIZADO (com barra de tarefas e botões)
                Window.fullscreen = False  # Não é tela cheia completa
                Window.show_cursor = True
                Window.state = 'maximized'  # Janela maximizada (mantém barra de tarefas)
                print("Modo PC ativado - janela maximizada com barra de tarefas e botões")
            
            # Configurações comuns
            Window.clearcolor = (1, 1, 1, 1)
            Window.borderless = False
            Window.resizable = True
            Window.always_on_top = False
            
            self.title = "Controle de Vendas"
            try:
                kv_path = os.path.join(os.path.dirname(__file__), 'app.kv')
                print(f"Carregando KV via caminho absoluto: {kv_path}")
                self.load_kv(kv_path)
                print("KV carregado")
            except Exception as kv_error:
                print(f"Erro KV: {kv_error}")
                import traceback
                traceback.print_exc()
                return None
            
            # Agendar tentativa de trazer janela para frente
            from kivy.clock import Clock
            def bring_to_front(dt):
                Window.raise_window()
            Clock.schedule_once(bring_to_front, 0.5)
            
            root = RootWidget()
            # Força inicial de seleção de aba (juntamente com on_kv_post)
            try:
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self._garantir_aba_login_visivel(root), 0.1)
            except Exception as e:
                print(f"Erro agendando garantia de aba: {e}")

            print("Aplicação pronta")
            return root
            
        except Exception as e:
            print(f"Erro build: {e}")
            return None

    def _garantir_aba_login_visivel(self, root):
        """Garante que a aba de login está realmente visível."""
        try:
            if not hasattr(root, 'ids') or 'tab_panel' not in root.ids:
                return
            
            tab_panel = root.ids.tab_panel
            login_tab = root.ids.get('login_tab')
            
            if login_tab is None:
                return
            
            # Forçar renderização da aba
            login_tab.disabled = False
            tab_panel.switch_to(login_tab)
            
            print("[_garantir_aba_login_visivel] Aba de login garantida em root com switch_to()")
        except Exception as e:
            print(f"[_garantir_aba_login_visivel] Erro: {e}")

            
        except Exception as e:
            print(f"Erro build: {e}")
            return None

    def _teste_popup(self, dt):
        """Testa abertura de popup para verificar se a aplicação está respondendo."""
        try:
            print("=== TENTANDO ABRIR POPUP DE TESTE ===")
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            from kivy.uix.button import Button
            from kivy.uix.boxlayout import BoxLayout
            
            content = BoxLayout(orientation='vertical')
            content.add_widget(Label(text='Aplicação funcionando!\nEsta é uma janela de teste.'))
            btn = Button(text='Fechar', size_hint_y=None, height=50)
            
            popup = Popup(title='Teste', content=content, size_hint=(0.8, 0.4))
            btn.bind(on_press=popup.dismiss)
            content.add_widget(btn)
            
            popup.open()
            print("✓ Popup aberto com sucesso")
        except Exception as e:
            print(f"❌ Erro ao abrir popup: {e}")
            import traceback
            traceback.print_exc()

    def on_start(self):
        """Chamado quando o aplicativo entra no ciclo principal."""
        print("[on_start] App começou loop principal")
        from kivy.clock import Clock

        # Agendar com múltiplos timestamps para garantir execução
        Clock.schedule_once(self._forcar_aba_login_2, 0.05)
        Clock.schedule_once(self._forcar_aba_login_2, 0.1)
        Clock.schedule_once(self._forcar_aba_login_2, 0.2)

    def _forcar_aba_login_2(self, dt):
        try:
            root = self.root
            if root is None or not hasattr(root, 'ids'):
                return

            if not ('tab_panel' in root.ids and 'login_tab' in root.ids):
                return

            tab_panel = root.ids.tab_panel
            login_tab = root.ids.login_tab

            # Garantir que a aba não está desabilitada
            login_tab.disabled = False
            if 'cadastro_tab' in root.ids:
                root.ids.cadastro_tab.disabled = False

            # Forçar a seleção via switch_to (current_tab é readonly)
            try:
                tab_panel.switch_to(login_tab)
                print(f"[on_start] Aba de login selecionada em dt={dt}")
            except Exception as switch_error:
                print(f"[on_start] Erro ao fazer switch_to em dt={dt}: {switch_error}")

        except Exception as e:
            print(f"[on_start] Erro em _forcar_aba_login_2 (dt={dt}): {e}")

    def on_stop(self):
        """
        Chamado quando a aplicação está sendo fechada.
        Realiza logout do usuário.
        """
        logger.info("Aplicação fechada - Logout automático realizado")
        return True


if __name__ == "__main__": 
    # Verificar se já existe outra instância rodando
    if not verificar_single_instance():
        print("\n" + "="*50)
        print("  ❌ ERRO: Aplicação já está em execução!")
        print("="*50)
        print("\nPenas uma instância do programa pode rodar por vez.")
        print("Feche a janela existente e tente novamente.\n")
        import sys
        sys.exit(1)
    
    app = VendasApp()
    app.run()