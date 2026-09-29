# modules/network.py
import subprocess
import re
import os

def get_interfaces():
    """
    Escanea el sistema buscando interfaces inalámbricas,
    detecta si están en modo monitor o managed y devuelve una lista de diccionarios.
    """
    interfaces = []
    try:
        # Ejecutamos iwconfig para ver las interfaces inalámbricas instaladas
        result = subprocess.run(["iwconfig"], capture_output=True, text=True, check=True)
        lines = result.stdout.split("\n")
        
        current_iface = None
        for line in lines:
            if not line:
                continue
            # Si la línea empieza con texto sin espacios, suele ser el nombre de la interfaz
            if not line.startswith(" "):
                match_name = re.match(r"^([a-zA-Z0-9]+)", line)
                if match_name:
                    current_iface = match_name.group(1)
            
            # Buscamos el modo de operación en las propiedades
            if "Mode:" in line and current_iface:
                match_mode = re.search(r"Mode:([a-zA-Z]+)", line)
                if match_mode:
                    mode = match_mode.group(1).lower()
                    is_monitor = (mode == "monitor")
                    interfaces.append({
                        "name": current_iface,
                        "monitor": is_monitor
                    })
                    current_iface = None
    except Exception as e:
        print(f"Error detectando interfaces: {e}")
        
    return interfaces

def toggle_monitor_mode(iface_name, current_state):
    """
    Cambia el estado de la interfaz. Si está en managed, la pasa a monitor.
    Si está en monitor, la regresa a managed. Usa comandos nativos estables.
    """
    # Sin shell: el nombre de la interfaz va como argumento y no como
    # texto que interprete /bin/sh. Además estos son exactamente los
    # tres comandos que autoriza /etc/sudoers.d/wifang.
    nuevo_tipo = "managed" if current_state else "monitor"
    comandos = [
        ["sudo", "ip", "link", "set", iface_name, "down"],
        ["sudo", "iw", "dev", iface_name, "set", "type", nuevo_tipo],
        ["sudo", "ip", "link", "set", iface_name, "up"],
    ]

    try:
        for comando in comandos:
            subprocess.run(comando, check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False
