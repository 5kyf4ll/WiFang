#!/bin/bash
# ============================================================
#  WiFang Uninstaller
#  Desinstala el servicio, las reglas sudoers, la config de
#  NetworkManager y (opcionalmente) el venv y los datos.
# ============================================================
set -euo pipefail

# ------------------------------------------------------------ #
#  Comprobaciones iniciales                                    #
# ------------------------------------------------------------ #
if [[ $EUID -ne 0 ]]; then
    echo "[!] Ejecuta con: sudo bash uninstall.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Desinstalando WiFang..."
echo ""

# ------------------------------------------------------------ #
#  Servicio systemd                                            #
# ------------------------------------------------------------ #
# FIX: antes usábamos "systemctl list-unit-files | grep" que
# fallaba silenciosamente porque systemd cambia el formato de
# salida entre versiones y puede usar pager. Ahora comprobamos
# directamente si el archivo existe, que es lo que realmente
# nos importa para poder borrarlo.
# ------------------------------------------------------------ #
if [[ -f /etc/systemd/system/wifang.service ]]; then
    echo "[*] Deteniendo servicio..."

    # Detener (silencioso si no estaba corriendo)
    systemctl stop wifang.service 2>/dev/null || true

    # Deshabilitar (elimina el symlink de multi-user.target.wants)
    systemctl disable wifang.service 2>/dev/null || true

    # Borrar el archivo del servicio
    rm -f /etc/systemd/system/wifang.service

    # FIX: borrar también el symlink por si "disable" falló
    rm -f /etc/systemd/system/multi-user.target.wants/wifang.service

    # Recargar systemd para que olvide el servicio
    systemctl daemon-reload

    # FIX: limpiar el estado "failed" para que "status" no muestre
    # restos del servicio en la siguiente consulta
    systemctl reset-failed wifang.service 2>/dev/null || true

    echo "[+] Servicio eliminado"
else
    echo "[*] Servicio no encontrado, nada que eliminar"
fi

# ------------------------------------------------------------ #
#  Regla sudoers                                               #
# ------------------------------------------------------------ #
if [[ -f /etc/sudoers.d/wifang ]]; then
    rm -f /etc/sudoers.d/wifang
    echo "[+] Regla sudoers eliminada"
else
    echo "[*] Regla sudoers no encontrada"
fi

# ------------------------------------------------------------ #
#  NetworkManager                                              #
# ------------------------------------------------------------ #
if [[ -f /etc/NetworkManager/conf.d/wifang.conf ]]; then
    rm -f /etc/NetworkManager/conf.d/wifang.conf
    systemctl reload NetworkManager 2>/dev/null || true
    echo "[+] Configuración de NetworkManager eliminada"
else
    echo "[*] Configuración de NetworkManager no encontrada"
fi

# ------------------------------------------------------------ #
#  Entorno virtual                                             #
# ------------------------------------------------------------ #
read -p "¿Borrar también el entorno virtual? [s/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    if [[ -d "$PROJECT_DIR/venv" ]]; then
        rm -rf "$PROJECT_DIR/venv"
        echo "[+] venv eliminado"
    else
        echo "[*] venv no encontrado"
    fi
fi

# ------------------------------------------------------------ #
#  Datos del usuario                                           #
# ------------------------------------------------------------ #
read -p "¿Borrar cracked.json, hs/ y logs? [s/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    rm -f  "$PROJECT_DIR/cracked.json"
    rm -rf "$PROJECT_DIR/hs"
    rm -f  "$PROJECT_DIR/wifang.log"
    echo "[+] Datos eliminados"
fi

# ------------------------------------------------------------ #
#  Fin                                                         #
# ------------------------------------------------------------ #
echo ""
echo "[+] Desinstalación completa."
echo "    Para reinstalar: sudo bash install.sh"
