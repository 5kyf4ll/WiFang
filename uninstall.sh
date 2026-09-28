#!/bin/bash
# ============================================================
#  WiFang Uninstaller
# ============================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "[!] Ejecuta con: sudo bash uninstall.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Desinstalando WiFang..."
echo ""

# Detener y deshabilitar servicio
if systemctl list-unit-files | grep -q "^wifang.service"; then
    echo "[*] Deteniendo servicio..."
    systemctl stop wifang.service 2>/dev/null || true
    systemctl disable wifang.service 2>/dev/null || true
    rm -f /etc/systemd/system/wifang.service
    systemctl daemon-reload
    echo "[+] Servicio eliminado"
fi

# Sudoers
if [[ -f /etc/sudoers.d/wifang ]]; then
    rm -f /etc/sudoers.d/wifang
    echo "[+] Regla sudoers eliminada"
fi

# NetworkManager conf
if [[ -f /etc/NetworkManager/conf.d/wifang.conf ]]; then
    rm -f /etc/NetworkManager/conf.d/wifang.conf
    systemctl reload NetworkManager 2>/dev/null || true
    echo "[+] Configuración de NetworkManager eliminada"
fi

# Venv
read -p "¿Borrar también el entorno virtual? [s/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    rm -rf "$PROJECT_DIR/venv"
    echo "[+] venv eliminado"
fi

# Datos del usuario
read -p "¿Borrar cracked.json, hs/ y logs? [s/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    rm -f  "$PROJECT_DIR/cracked.json"
    rm -rf "$PROJECT_DIR/hs"
    rm -f  "$PROJECT_DIR/wifang.log"
    echo "[+] Datos eliminados"
fi

echo ""
echo "[+] Desinstalación completa."
echo "    Para reinstalar: sudo bash install.sh"