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
#                                                              #
# Las rutas se resuelven en el sistema en vez de fijarse a     #
# mano: en Debian / Raspberry Pi OS 'iw' vive en /usr/sbin y   #
# 'aircrack-ng' en /usr/bin, así que las rutas fijas no        #
# coincidían y sudo pedía contraseña.                          #
#                                                              #
# 'ip' e 'iw' llevan los argumentos acotados a las operaciones #
# que ejecuta modules/network.py. Un NOPASSWD sobre 'ip'       #
# completo permite 'sudo ip netns exec <ns> /bin/sh'.          #
# ------------------------------------------------------------ #

BIN_DIRS=(/usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin)

# Rutas existentes de un binario, en el mismo orden de prioridad
# que el secure_path de sudo. Debian instala 'ip' tanto en
# /usr/bin como en /usr/sbin (son ficheros distintos) y sudo
# resuelve por secure_path, así que hay que cubrir las dos.
# Se omiten los alias por enlace simbólico (/sbin -> /usr/sbin).
find_paths() {
    local name="$1" dir real
    local -A vistos=()
    for dir in "${BIN_DIRS[@]}"; do
        [[ -x "$dir/$name" ]] || continue
        real=$(readlink -f "$dir/$name")
        [[ -n "${vistos[$real]:-}" ]] && continue
        vistos[$real]=1
        printf '%s\n' "$dir/$name"
    done
    return 0
}

RULES=""

add_rule() {
    RULES+="$REAL_USER ALL=(ALL) NOPASSWD: $1"$'\n'
}

# ------------------------------------------------------------ #
#  Gestión de interfaces de red                                #
# ------------------------------------------------------------ #
RULES+=$'# Gestión de interfaces de red (argumentos acotados)\n'

while IFS= read -r bin; do
    [[ -n "$bin" ]] || continue
    add_rule "$bin link set * up"
    add_rule "$bin link set * down"
done < <(find_paths ip)

while IFS= read -r bin; do
    [[ -n "$bin" ]] || continue
    add_rule "$bin dev * set type monitor"
    add_rule "$bin dev * set type managed"
done < <(find_paths iw)

# ------------------------------------------------------------ #
#  Herramientas de pentesting y apagado                        #
# ------------------------------------------------------------ #
RULES+=$'\n# Herramientas de pentesting y sistema\n'

for tool in airmon-ng airodump-ng aireplay-ng aircrack-ng rfkill \
            wifite wash reaver bully hcxdumptool hcxpcapngtool \
            shutdown reboot; do
    found=0
    while IFS= read -r bin; do
        [[ -n "$bin" ]] || continue
        add_rule "$bin"
        found=1
    done < <(find_paths "$tool")
    if [[ $found -eq 0 ]]; then
        echo "[!] $tool no está instalado: sin regla sudoers"
    fi
done

# ------------------------------------------------------------ #
#  Escribir el fichero                                         #
# ------------------------------------------------------------ #
echo "[*] Escribiendo regla sudoers en $SUDOERS_FILE"

cat > "$SUDOERS_FILE" <<EOF
# WiFang - permisos sin contraseña
# Generado automáticamente por install.sh

$RULES
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
