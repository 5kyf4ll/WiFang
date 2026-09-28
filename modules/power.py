# modules/power.py
import subprocess
import time
import RPi.GPIO as GPIO

import config
from gui import oled_menu


# ------------------------------------------------------------------ #
#  ACCIONES                                                          #
# ------------------------------------------------------------------ #
def _do_shutdown():
    oled_menu.show_message("APAGANDO...", "Espera 5 segundos", "antes de desconectar")
    time.sleep(1.5)
    subprocess.run(["shutdown", "-h", "now"])


def _do_reboot():
    oled_menu.show_message("REINICIANDO...", "WiFang volvera", "en unos segundos")
    time.sleep(1.5)
    subprocess.run(["reboot"])


# ------------------------------------------------------------------ #
#  CONFIRMACIÓN                                                      #
# ------------------------------------------------------------------ #
def _confirm(action_name):
    """
    Muestra pantalla de confirmación.
    Devuelve True si el usuario confirma con SELECT, False si cancela con UP/DOWN.
    """
    oled_menu.clear_screen()
    oled_menu.draw.rectangle((0, 0, oled_menu.W - 1, 11), fill=255)
    oled_menu.draw.text((3, 0), f"¿{action_name}?", font=oled_menu.font_title, fill=0)

    oled_menu.draw.text((6, 20), "SELECT = Confirmar", font=oled_menu.font, fill=255)
    oled_menu.draw.text((6, 34), "UP/DOWN = Cancelar", font=oled_menu.font, fill=255)

    oled_menu.draw.text((6, 52), "Esperando...", font=oled_menu.font_small, fill=255)
    oled_menu.refresh()

    # Esperar a que el usuario suelte el botón que lo trajo aquí
    while GPIO.input(config.BTN_SELECT) == GPIO.LOW:
        time.sleep(0.05)

    # Esperar decisión
    while True:
        if GPIO.input(config.BTN_SELECT) == GPIO.LOW:
            time.sleep(0.3)
            return True
        if (GPIO.input(config.BTN_UP) == GPIO.LOW or
            GPIO.input(config.BTN_DOWN) == GPIO.LOW):
            time.sleep(0.3)
            return False
        time.sleep(0.05)


# ------------------------------------------------------------------ #
#  MENÚ PRINCIPAL DEL MÓDULO                                         #
# ------------------------------------------------------------------ #
def start_power_loop():
    """
    Submenú con Apagar / Reiniciar / Volver.
    Ambos con confirmación.
    """
    items = ["Apagar", "Reiniciar", "<- VOLVER"]
    index = 0

    while True:
        oled_menu.draw_menu("ENERGIA", items, index, icon="⏻")

        if GPIO.input(config.BTN_UP) == GPIO.LOW:
            index = (index - 1) % len(items)
            time.sleep(0.2)
        elif GPIO.input(config.BTN_DOWN) == GPIO.LOW:
            index = (index + 1) % len(items)
            time.sleep(0.2)
        elif GPIO.input(config.BTN_SELECT) == GPIO.LOW:
            time.sleep(0.3)

            if index == 2:                          # Volver
                return

            elif index == 0:                        # Apagar
                if _confirm("Apagar WiFang"):
                    _do_shutdown()
                    # Si por algún motivo el shutdown falla, evitamos bucle
                    time.sleep(60)
                else:
                    oled_menu.show_message("CANCELADO", "Apagado", "cancelado")
                    time.sleep(1)

            elif index == 1:                        # Reiniciar
                if _confirm("Reiniciar WiFang"):
                    _do_reboot()
                    time.sleep(60)
                else:
                    oled_menu.show_message("CANCELADO", "Reinicio", "cancelado")
                    time.sleep(1)

        time.sleep(0.05)
