# gui/oled_menu.py
import os
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import config

# ------------------------------------------------------------------ #
#  HARDWARE                                                          #
# ------------------------------------------------------------------ #
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(
    config.SCREEN_WIDTH, config.SCREEN_HEIGHT, i2c, addr=config.OLED_ADDR
)
W, H = config.SCREEN_WIDTH, config.SCREEN_HEIGHT

image = Image.new("1", (W, H))
draw = ImageDraw.Draw(image)

# ------------------------------------------------------------------ #
#  FUENTES (con fallback si no existen)                              #
# ------------------------------------------------------------------ #
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
]

def _load_font(size):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()   # último recurso

font_small = _load_font(9)
font       = _load_font(10)   # compatibilidad con módulos existentes
font_title = _load_font(10)

# ------------------------------------------------------------------ #
#  LOGO                                                              #
# ------------------------------------------------------------------ #
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH   = os.path.join(CURRENT_DIR, "assets", "logo.png")
_logo_cache = None

def _load_logo():
    """Carga el logo PNG, lo ajusta al tamaño de pantalla y lo cachea."""
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache

    if not os.path.exists(LOGO_PATH):
        print(f"[!] Logo no encontrado en {LOGO_PATH}")
        return None

    try:
        img = Image.open(LOGO_PATH).convert("L")
        img = img.resize((W, H), Image.LANCZOS)
        img = img.point(lambda p: 255 if p > 128 else 0)
        _logo_cache = img.convert("1")
        return _logo_cache
    except Exception as e:
        print(f"[!] Error cargando logo: {e}")
        return None

def draw_logo():
    """Dibuja el logo a pantalla completa. Devuelve True si lo encontró."""
    clear_screen()
    logo = _load_logo()
    if logo is None:
        # Fallback si no hay PNG: pinta el nombre con la fuente title
        draw.text((28, 26), "WiFang", font=font_title, fill=255)
        refresh()
        return False

    image.paste(logo, (0, 0))
    refresh()
    return True

# ------------------------------------------------------------------ #
#  HELPERS INTERNOS                                                  #
# ------------------------------------------------------------------ #
HEADER_H = 13

def _text_size(txt, f):
    """Devuelve (ancho, alto) de un texto. Compatible con Pillow viejo/nuevo."""
    try:
        bbox = draw.textbbox((0, 0), txt, font=f)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(txt, font=f)

def _fit(text, max_px, f):
    """Trunca con '…' si excede max_px."""
    if _text_size(text, f)[0] <= max_px:
        return text
    ell = "…"
    ell_w = _text_size(ell, f)[0]
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_size(text[:mid], f)[0] + ell_w <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell

def _draw_header(title, icon="►", right_text=""):
    """Barra superior invertida tipo app móvil."""
    draw.rectangle((0, 0, W, HEADER_H), outline=0, fill=255)

    # Texto de la derecha (ej: "2/5")
    rw = 0
    if right_text:
        rw, _ = _text_size(right_text, font_small)
        draw.text((W - rw - 3, 3), right_text, font=font_small, fill=0)

    # Título a la izquierda
    label = f"{icon} {title}".strip()
    label = _fit(label, W - rw - 8, font_title)
    draw.text((3, 1), label, font=font_title, fill=0)

# ------------------------------------------------------------------ #
#  API PÚBLICA (compatible con tus módulos)                          #
# ------------------------------------------------------------------ #
def clear_screen():
    draw.rectangle((0, 0, W, H), outline=0, fill=0)

def refresh():
    oled.image(image)
    oled.show()

def draw_menu(title, items, current_index, icon="►"):
    """Menú vertical con selección invertida, scrollbar y contador."""
    clear_screen()

    page = f"{current_index + 1}/{len(items)}" if items else "0/0"
    _draw_header(title, icon=icon, right_text=page)

    # --- Área de items ---
    top      = HEADER_H + 3
    bottom   = H - 2
    row_h    = 11
    max_rows = max(1, (bottom - top + 1) // row_h)

    # --- Ajustes de la barra de selección ---
    SELECTOR_UP   = 0    # cuánto sube por encima del texto
    SELECTOR_DOWN = 12   # cuánto baja por debajo del texto

    start = 0
    if current_index >= max_rows:
        start = current_index - max_rows + 1
    end = min(len(items), start + max_rows)

    for i, idx in enumerate(range(start, end)):
        y = top + i * row_h
        selected = (idx == current_index)
        label = _fit(items[idx], W - 10, font)

        if selected:
            draw.rectangle(
                (0, y + SELECTOR_UP, W - 5, y + SELECTOR_DOWN),
                fill=255
            )
            draw.text((4, y), label, font=font, fill=0)
        else:
            draw.text((4, y), label, font=font, fill=255)

    # --- Scrollbar lateral (solo si hay overflow) ---
    if len(items) > max_rows:
        x = W - 3
        bar_top = top - 1
        bar_bot = bottom + 1
        track_h = bar_bot - bar_top

        # pista
        draw.rectangle((x, bar_top, x + 2, bar_bot), outline=0, fill=0)
        draw.line((x + 1, bar_top, x + 1, bar_bot), fill=255)

        # thumb
        thumb_h = max(6, track_h * max_rows // len(items))
        denom   = max(1, len(items) - 1)
        thumb_y = bar_top + (track_h - thumb_h) * current_index // denom
        draw.rectangle((x, thumb_y, x + 2, thumb_y + thumb_h), fill=255)

    refresh()

def show_message(line1, line2="", line3="", icon=""):
    """Mensaje centrado con marco, título destacado y cuerpo."""
    clear_screen()

    # Marco exterior fino
    draw.rectangle((0, 0, W - 1, H - 1), outline=255, fill=0)

    # Título centrado
    title = f"{icon} {line1}".strip() if icon else line1
    title = _fit(title, W - 8, font_title)
    tw, _ = _text_size(title, font_title)
    draw.text(((W - tw) // 2, 3), title, font=font_title, fill=255)

    # Separador
    draw.line((4, 17, W - 5, 17), fill=255)

    # Cuerpo (2 líneas opcionales)
    y = 22
    for txt in (line2, line3):
        if not txt:
            continue
        txt_fit = _fit(txt, W - 8, font)
        tw, _ = _text_size(txt_fit, font)
        draw.text(((W - tw) // 2, y), txt_fit, font=font, fill=255)
        y += 13

    refresh()

def draw_wrapped_text(text, start_y, max_chars=20, center=False):
    """Igual que antes, pero con centrado opcional. No hace refresh."""
    lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    for i, line in enumerate(lines):
        x = 0
        if center:
            tw, _ = _text_size(line, font)
            x = max(0, (W - tw) // 2)
        draw.text((x, start_y + i * 10), line, font=font, fill=255)

# ------------------------------------------------------------------ #
#  EXTRAS (opcionales)                                               #
# ------------------------------------------------------------------ #
def draw_startup_banner(name="WiFang", subtitle="WiFi Pentest Toolkit"):
    """Pantalla de arranque con doble borde y branding (fallback)."""
    clear_screen()
    draw.rectangle((0, 0, W - 1, H - 1), outline=255, fill=0)
    draw.rectangle((2, 2, W - 3, H - 3), outline=255, fill=0)

    tw, _ = _text_size(name, font_title)
    draw.text(((W - tw) // 2, 18), name, font=font_title, fill=255)

    tw, _ = _text_size(subtitle, font_small)
    draw.text(((W - tw) // 2, 34), subtitle, font=font_small, fill=255)

    draw.text((6, 50), "v2.0  •  RPi Zero W", font=font_small, fill=255)
    refresh()

def draw_progress_bar(pct, label="", y=42):
    """Barra de progreso horizontal para escaneos."""
    pct = max(0, min(100, pct))
    x0, x1 = 4, W - 5
    box_w = x1 - x0

    if label:
        lab = _fit(label, W - 8, font)
        tw, _ = _text_size(lab, font)
        draw.text(((W - tw) // 2, y - 14), lab, font=font, fill=255)

    draw.rectangle((x0, y, x1, y + 8), outline=255, fill=0)
    fill_w = int(box_w * pct / 100)
    if fill_w > 1:
        draw.rectangle((x0 + 1, y + 1, x0 + fill_w, y + 7), fill=255)
