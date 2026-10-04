# main.py
import RPi.GPIO as GPIO
import time
import config
from gui import oled_menu
from modules import network
from modules import attack_wps
from modules import attack_handshake
from modules import saved
from modules import power                     # <- NUEVO

# ------------------------------------------------------------------ #
#  CONFIGURACIÓN DE BOTONES FÍSICOS                                  #
# ------------------------------------------------------------------ #
GPIO.setmode(GPIO.BCM)
for btn in [config.BTN_UP, config.BTN_DOWN, config.BTN_SELECT]:
    GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ------------------------------------------------------------------ #
#  MENÚ PRINCIPAL                                                    #
# ------------------------------------------------------------------ #
menu_options = [
    "Modo Monitor",
    "Handshake",
    "WPS Attack",
    "Guardados",
    "Energia",                                # <- NUEVO
]
current_selection = 0


def auto_check_network():
    """Verifica al arrancar si ya existe una tarjeta en modo monitor."""
    oled_menu.show_message("WiFang v2.0", "Buscando antenas...", "Espere un momento")
    time.sleep(1)

    ifaces = network.get_interfaces()
    for iface in ifaces:
        if iface["monitor"]:
            config.INTERFACE = iface["name"]
            oled_menu.show_message("AUTO DETECTADO", f"Activa: {iface['name']}", "Listo para usar")
            time.sleep(1.5)
            return

    oled_menu.show_message("AVISO HARDWARE", "Ninguna antena", "esta en Monitor")
    time.sleep(1.5)


def interfaces_menu_loop():
    """Menú dinámico de gestión de hardware inalámbrico."""
    iface_idx = 0
    while True:
        ifaces = network.get_interfaces()
        if not ifaces:
            oled_menu.show_message("ERROR HARDWARE", "No se detectan", "tarjetas WiFi")
            time.sleep(2)
            break

        items_text = []
        for iface in ifaces:
            status_indicator = " [*]" if iface["monitor"] else ""
            active_indicator = " (Activa)" if config.INTERFACE == iface["name"] else ""
            items_text.append(f"{iface['name']}{status_indicator}{active_indicator}")

        items_text.append("<- VOLVER")

        oled_menu.draw_menu("GESTION ANTENAS", items_text, iface_idx)

        if GPIO.input(config.BTN_UP) == GPIO.LOW:
            iface_idx = (iface_idx - 1) % len(items_text)
            time.sleep(0.2)
        elif GPIO.input(config.BTN_DOWN) == GPIO.LOW:
            iface_idx = (iface_idx + 1) % len(items_text)
            time.sleep(0.2)
        elif GPIO.input(config.BTN_SELECT) == GPIO.LOW:
            time.sleep(0.3)

            if iface_idx == len(items_text) - 1:
                break

            selected_iface = ifaces[iface_idx]
            oled_menu.show_message("CAMBIANDO MODO", "Configurando...", selected_iface["name"])

            success = network.toggle_monitor_mode(selected_iface["name"], selected_iface["monitor"])
            if success:
                if not selected_iface["monitor"]:
                    config.INTERFACE = selected_iface["name"]
                elif config.INTERFACE == selected_iface["name"]:
                    config.INTERFACE = ""
                oled_menu.show_message("PROCESO EXITOSO", "Cambio aplicado", "correctamente")
            else:
                oled_menu.show_message("ERROR SISTEMA", "No se pudo cambiar", "el modo")
            time.sleep(1.5)


def main_menu_loop():
    global current_selection

    # Intro: logo WiFang
    oled_menu.draw_logo()
    time.sleep(1.5)

    # Autodetección de hardware al arrancar
    auto_check_network()

    while True:
        oled_menu.draw_menu("HACK WIFI", menu_options, current_selection)

        if GPIO.input(config.BTN_UP) == GPIO.LOW:
            current_selection = (current_selection - 1) % len(menu_options)
            time.sleep(0.2)

        elif GPIO.input(config.BTN_DOWN) == GPIO.LOW:
            current_selection = (current_selection + 1) % len(menu_options)
            time.sleep(0.2)

        elif GPIO.input(config.BTN_SELECT) == GPIO.LOW:
            time.sleep(0.3)

            if current_selection == 0:
                interfaces_menu_loop()

            elif current_selection == 1:
                if not config.INTERFACE:
                    oled_menu.show_message("ATENCION", "Primero activa", "un modo monitor")
                    time.sleep(2)
                else:
                    attack_handshake.start_handshake_attack_loop()
                    time.sleep(0.3)

            elif current_selection == 2:
                if not config.INTERFACE:
                    oled_menu.show_message("ATENCION", "Primero activa", "un modo monitor")
                    time.sleep(2)
                else:
                    attack_wps.start_wps_attack_loop()
                    time.sleep(0.3)

            elif current_selection == 3:
                saved.start_saved_loop()
                time.sleep(0.3)

            elif current_selection == 4:                # <- NUEVO
                power.start_power_loop()
                time.sleep(0.3)

        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main_menu_loop()
    except KeyboardInterrupt:
        pass
    finally:
        oled_menu.clear_screen()
        oled_menu.refresh()
        GPIO.cleanup()
