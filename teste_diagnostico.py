#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Versão diagnóstica da aplicação para rastrear problemas de renderização
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty, DictProperty, NumericProperty
import os

class RootWidget(BoxLayout):
    # Propriedades esperadas pelo KV
    clientes = ListProperty([])
    produtos = ListProperty([])
    clientes_spinner_values = ListProperty([])
    produtos_spinner_values = ListProperty([])
    status_log = StringProperty("Iniciado")
    pedidos = ListProperty([])
    vendedor = DictProperty({})
    total_vendas = NumericProperty(0.0)
    comissao = NumericProperty(0.0)
    def on_kv_post(self, *args):
        print("[on_kv_post] Iniciado")
        try:
            if hasattr(self.ids, 'tab_panel'):
                tab_panel = self.ids.tab_panel
                print(f"[on_kv_post] TabbedPanel encontrado: {tab_panel}")
                print(f"[on_kv_post] TabbedPanel size: {tab_panel.size}")
                print(f"[on_kv_post] TabbedPanel pos: {tab_panel.pos}")
                print(f"[on_kv_post] TabbedPanel size_hint: {tab_panel.size_hint}")
                print(f"[on_kv_post] TabbedPanel opacity: {tab_panel.opacity}")
                print(f"[on_kv_post] TabbedPanel canvas: {tab_panel.canvas}")
                
                # Listar abas
                print(f"[on_kv_post] Número de abas: {len(tab_panel.tab_list)}")
                for i, tab in enumerate(tab_panel.tab_list):
                    print(f"[on_kv_post]   Aba {i}: {tab.text}")
                
                # Tentar selecionarlogin_tab
                if hasattr(self.ids, 'login_tab'):
                    login_tab = self.ids.login_tab
                    print(f"[on_kv_post] Login tab encontrada: {login_tab}")
                    print(f"[on_kv_post] Login tab size: {login_tab.size}")
                    print(f"[on_kv_post] Login tab pos: {login_tab.pos}")
                    print(f"[on_kv_post] Login tab opacity: {login_tab.opacity}")
                    print(f"[on_kv_post] Login tab disabled: {login_tab.disabled}")
                    
                    # Tentar switch_to
                    try:
                        tab_panel.switch_to(login_tab)
                        print(f"[on_kv_post] switch_to executado com sucesso")
                    except Exception as e:
                        print(f"[on_kv_post] Erro em switch_to: {e}")
                
                # Agendar verificações posteriores
                Clock.schedule_once(self.check_tab_status, 0.1)
                Clock.schedule_once(self.check_tab_status, 0.5)
                Clock.schedule_once(self.check_tab_status, 1.0)
        except Exception as e:
            print(f"[on_kv_post] Erro: {e}")
            import traceback
            traceback.print_exc()
    
    def check_tab_status(self, dt):
        print(f"\n[check_tab_status @ {dt}s]")
        try:
            if hasattr(self.ids, 'tab_panel'):
                tab_panel = self.ids.tab_panel
                print(f"  Tab panel current_tab: {tab_panel.current_tab}")
                print(f"  Tab panel size: {tab_panel.size}")
                print(f"  Tab panel pos: {tab_panel.pos}")
                print(f"  Tab panel opacity: {tab_panel.opacity}")
                
                if tab_panel.current_tab:
                    content = tab_panel.current_tab.content
                    print(f"  Current tab content: {content}")
                    if content:
                        print(f"    Content size: {content.size}")
                        print(f"    Content pos: {content.pos}")
                        print(f"    Content opacity: {content.opacity}")
        except Exception as e:
            print(f"  Erro: {e}")


class DiagnosticApp(App):
    def build(self):
        print("[build] Iniciado")
        
        # Configurar janela
        Window.size = (1000, 700)
        Window.clearcolor = (1, 1, 1, 1)
        self.title = "Teste Diagnóstico"
        
        print("[build] Carregando KV...")
        kv_path = os.path.join(os.path.dirname(__file__), 'app.kv')
        try:
            self.load_kv(kv_path)
            print("[build] KV carregado com sucesso")
        except Exception as e:
            print(f"[build] Erro ao carregar KV: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        root = RootWidget()
        print("[build] RootWidget criado")
        
        # Agendar check após alguns milissegundos
        Clock.schedule_once(lambda dt: print(f"\n[APP Status @ {dt}s] Root size: {root.size}, Root pos: {root.pos}"), 0.3)
        
        return root

if __name__ == '__main__':
    print("Iniciando aplicação diagnóstica...")
    app = DiagnosticApp()
    app.run()
