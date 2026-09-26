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
    try:
        if not current_state:
            # Pasar a modo Monitor de forma limpia y directa
            subprocess.run(f"sudo ip link set {iface_name} down", shell=True, check=True)
            subprocess.run(f"sudo iw dev {iface_name} set type monitor", shell=True, check=True)
            subprocess.run(f"sudo ip link set {iface_name} up", shell=True, check=True)
        else:
            # Regresar a modo Managed (Estándar)
            subprocess.run(f"sudo ip link set {iface_name} down", shell=True, check=True)
            subprocess.run(f"sudo iw dev {iface_name} set type managed", shell=True, check=True)
            subprocess.run(f"sudo ip link set {iface_name} up", shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
