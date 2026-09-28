#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

REAL_USER="$1"
SUDOERS_FILE="/etc/sudoers.d/wifang"

# ------------------------------------------------------------ #
#  Regla sudoers (acotada a los binarios que usa WiFang)       #
# ------------------------------------------------------------ #
# Nota: si el servicio systemd corre como root, esta regla es  #
# un extra de seguridad. Aun así la dejamos por si ejecutas    #
# main.py manualmente desde terminal.                          #
# ------------------------------------------------------------ #

echo "[*] Escribiendo regla sudoers en $SUDOERS_FILE"

cat > "$SUDOERS_FILE" <<EOF
# WiFang - permisos sin contraseña
# Generado automáticamente por install.sh

# Gestión de interfaces de red
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/airmon-ng
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/airodump-ng
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/aireplay-ng
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/aircrack-ng
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/iw
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/ip
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/rfkill

# Herramientas de pentesting
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/wifite
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/wifite
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/wash
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/reaver
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/bully
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/hcxdumptool
$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/hcxpcapngtool

# Sistema (apagado / reinicio)
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/reboot
$REAL_USER ALL=(ALL) NOPASSWD: /sbin/shutdown
$REAL_USER ALL=(ALL) NOPASSWD: /sbin/reboot
EOF

# ------------------------------------------------------------ #
#  Permisos correctos                                          #
# ------------------------------------------------------------ #
chmod 0440 "$SUDOERS_FILE"
chown root:root "$SUDOERS_FILE"

# ------------------------------------------------------------ #
#  Validar sintaxis                                            #
# ------------------------------------------------------------ #
if visudo -c -f "$SUDOERS_FILE" >/dev/null 2>&1; then
    echo "[+] Regla sudoers válida"
else
    echo "[-] Error de sintaxis en $SUDOERS_FILE. Eliminando..."
    rm -f "$SUDOERS_FILE"
    exit 1
fi

echo "[+] Regla sudoers instalada en $SUDOERS_FILE"
