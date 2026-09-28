# modules/saved.py
import os
import json
import time
import RPi.GPIO as GPIO

import config
from gui import oled_menu

# ------------------------------------------------------------------ #
#  RUTAS                                                             #
# ------------------------------------------------------------------ #
CURRENT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)      # ~/wifi
CRACKED_PATH = os.path.join(PROJECT_ROOT, "cracked.json")


# ------------------------------------------------------------------ #
#  CARGA Y PARSEO DE cracked.json                                    #
# ------------------------------------------------------------------ #
def _load_cracked():
    """
    Wifite genera cracked.json como objetos concatenados, no como array.
    Ejemplo:
        { ... },
        { ... },
    Esta función lo tolera todo:
      - Un único objeto.
      - Un array bien formado.
      - Objetos concatenados con comas (formato wifite).
    """
    if not os.path.exists(CRACKED_PATH):
        return []

    try:
        with open(CRACKED_PATH, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except Exception as e:
        print(f"[!] Error leyendo cracked.json: {e}")
        return []

    if not raw:
        return []

    # Intento 1: JSON válido (objeto único o array)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Intento 2: multi-objeto sin array (formato de wifite)
    cleaned = raw
    while cleaned.endswith(","):
        cleaned = cleaned[:-1].rstrip()

    try:
        data = json.loads("[" + cleaned + "]")
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as e:
        print(f"[!] cracked.json malformado: {e}")

    return []


def _format_date(ts):
    """Convierte un timestamp Unix a 'YYYY-MM-DD'. Devuelve '' si falla."""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(ts)))
    except Exception:
        return ""


# ------------------------------------------------------------------ #
#  DETALLE (pantalla de una red)                                     #
# ------------------------------------------------------------------ #
def _draw_detail(red):
    """Pantalla completa con la info de una red guardada."""
    oled_menu.clear_screen()

    # --- Header invertido con el ESSID ---
    oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
    essid = (red.get("essid") or "Oculta")[:20]
    oled_menu.draw.text((2, 0), essid, font=oled_menu.font_title, fill=0)

    # --- BSSID ---
    bssid = red.get("bssid", "")
    oled_menu.draw.text((2, 14), bssid, font=oled_menu.font_small, fill=255)

    # --- Fecha ---
    fecha = _format_date(red.get("date", 0))
    if fecha:
        oled_menu.draw.text((2, 24), fecha, font=oled_menu.font_small, fill=255)

    # --- Separador ---
    oled_menu.draw.line((2, 36, oled_menu.W - 3, 36), fill=255)

    # --- Password (grande y envuelto) ---
    key = red.get("key", "") or "(sin clave)"
    oled_menu.draw.text((2, 39), "KEY:", font=oled_menu.font_small, fill=255)
    oled_menu.draw_wrapped_text(key, 50, max_chars=20)

    oled_menu.refresh()


# ------------------------------------------------------------------ #
#  BUCLE PRINCIPAL                                                   #
# ------------------------------------------------------------------ #
def start_saved_loop():
    """Muestra las redes guardadas en cracked.json con su contraseña."""
    redes = _load_cracked()

    if not redes:
        oled_menu.show_message("SIN REGISTROS", "No hay redes", "guardadas aun")
        time.sleep(2)
        return

    # Ordenar por fecha descendente (más reciente primero)
    redes.sort(key=lambda r: int(r.get("date", 0) or 0), reverse=True)

    items_menu = ["<- VOLVER"]
    for r in redes:
        essid = (r.get("essid") or "Oculta")[:20]
        items_menu.append(essid)

    estado  = "LISTA"
    index   = 0
    target  = None

    while True:
        # ---------------------------------------------- #
        # ESTADO 1: LISTA                                 #
        # ---------------------------------------------- #
        if estado == "LISTA":
            oled_menu.draw_menu("GUARDADOS", items_menu, index, icon="★")

            if GPIO.input(config.BTN_UP) == GPIO.LOW:
                index = (index - 1) % len(items_menu)
                time.sleep(0.2)
            elif GPIO.input(config.BTN_DOWN) == GPIO.LOW:
                index = (index + 1) % len(items_menu)
                time.sleep(0.2)
            elif GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                time.sleep(0.3)

                if index == 0:
                    return

                target = redes[index - 1]
                estado = "DETALLE"
                time.sleep(0.15)

        # ---------------------------------------------- #
        # ESTADO 2: DETALLE                               #
        # ---------------------------------------------- #
        elif estado == "DETALLE":
            _draw_detail(target)

            # SELECT o UP: volver a la lista
            if (GPIO.input(config.BTN_SELECT) == GPIO.LOW or
                GPIO.input(config.BTN_UP) == GPIO.LOW):
                time.sleep(0.3)
                estado = "LISTA"

            # DOWN: siguiente red guardada (navegación rápida)
            elif GPIO.input(config.BTN_DOWN) == GPIO.LOW:
                index = index % len(redes) + 1    # 1..len(redes)
                target = redes[index - 1]
                time.sleep(0.25)

        time.sleep(0.05)


if __name__ == "__main__":
    # Prueba sin OLED: solo imprime lo que encuentra
    datos = _load_cracked()
    print(f"[+] {len(datos)} redes guardadas:")
    for r in datos:
        print(f"  - {r.get('essid', '?')} ({r.get('bssid', '?')}) "
              f"key={r.get('key', '?')} fecha={_format_date(r.get('date', 0))}")
