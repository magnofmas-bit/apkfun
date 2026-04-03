#!/usr/bin/env python3
"""
Script para gerar ícones do app Controle de Vendas
Execução: python gerar_icones.py
"""

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    print("✅ Pillow encontrado")
except ImportError:
    print("❌ Pillow não instalado. Instalando...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

# Criar pasta data se não existir
data_dir = Path(__file__).parent / "data"
data_dir.mkdir(exist_ok=True)

print("\n🎨 Gerando ícones...")

# ============================
# ÍCONE (192x192)
# ============================
icon = Image.new("RGB", (192, 192), color=(0, 116, 217))
draw = ImageDraw.Draw(icon)

# Desenhar círculo branco
draw.ellipse([(10, 10), (182, 182)], fill=(255, 255, 255))

# Tentar usar fonte do sistema
try:
    # Windows
    font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 80)
except:
    try:
        # Linux/Mac
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
    except:
        font = ImageFont.load_default()

# Desenhar texto "CV"
draw.text((72, 60), "CV", fill=(0, 116, 217), font=font)

icon_path = data_dir / "icon.png"
icon.save(icon_path)
print(f"✅ icon.png criado: {icon_path}")

# ============================
# SPLASH SCREEN (1280x720)
# ============================
splash = Image.new("RGB", (1280, 720), color=(0, 116, 217))
draw = ImageDraw.Draw(splash)

# Fontes
try:
    font_title = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 60)
    font_subtitle = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 30)
except:
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()

# Desenhar fundo com gradiente (simulado)
for y in range(720):
    ratio = y / 720
    r = int(0 * (1 - ratio) + 50 * ratio)
    g = int(116 * (1 - ratio) + 130 * ratio)
    b = int(217 * (1 - ratio) + 200 * ratio)
    draw.line([(0, y), (1280, y)], fill=(r, g, b))

# Título
draw.text((200, 250), "Controle de Vendas", fill=(255, 255, 255), font=font_title)

# Subtítulo
draw.text((250, 350), "Iniciando aplicação...", fill=(200, 200, 200), font=font_subtitle)

splash_path = data_dir / "presplash.png"
splash.save(splash_path)
print(f"✅ presplash.png criado: {splash_path}")

print("\n✅ Ícones gerados com sucesso!")
print("\n🔧 Próximo passo: executar 'buildozer android debug'")
