#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

REAL_USER="$1"

# ------------------------------------------------------------ #
#  Habilitar I2C                                               #
# ------------------------------------------------------------ #
echo "[*] Verificando I2C..."

if command_exists raspi-config; then
    # raspi-config nonint do_i2c 0 → habilita
    raspi-config nonint do_i2c 0 >/dev/null 2>&1 || true
    echo "[+] I2C habilitado vía raspi-config"
else
    # Fallback: editar config.txt manualmente
    for CFG in /boot/firmware/config.txt /boot/config.txt; do
        if [[ -f "$CFG" ]]; then
            if ! grep -q "^dtparam=i2c_arm=on" "$CFG"; then
                backup_file "$CFG"
                echo "dtparam=i2c_arm=on" >> "$CFG"
                echo "[+] Añadido dtparam=i2c_arm=on a $CFG"
            else
                echo "[*] I2C ya estaba habilitado en $CFG"
            fi
            break
        fi
    done
fi

# ------------------------------------------------------------ #
#  Añadir usuario a grupos útiles                              #
# ------------------------------------------------------------ #
echo "[*] Añadiendo $REAL_USER a grupos i2c, gpio, video..."
for grp in i2c gpio video plugdev netdev; do
    if getent group "$grp" >/dev/null; then
        usermod -aG "$grp" "$REAL_USER" 2>/dev/null || true
    fi
done

# ------------------------------------------------------------ #
#  Detectar antenas WiFi                                       #
# ------------------------------------------------------------ #
echo "[*] Antenas WiFi detectadas:"
if command_exists iw; then
    for iface in $(iw dev 2>/dev/null | awk '/Interface/ {print $2}'); do
        driver=$(basename "$(readlink -f /sys/class/net/$iface/device/driver 2>/dev/null)" 2>/dev/null || echo "?")
        echo "    - $iface (driver: $driver)"
    done
else
    echo "    (iw no instalado)"
fi

# ------------------------------------------------------------ #
#  Deshabilitar NetworkManager sobre wlan1 (si existe)         #
# ------------------------------------------------------------ #
NM_CONF="/etc/NetworkManager/conf.d/wifang.conf"
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    echo "[*] Configurando NetworkManager para no tocar wlan1..."
    mkdir -p /etc/NetworkManager/conf.d
    cat > "$NM_CONF" <<EOF
# WiFang - interfaces WiFi que NetworkManager NO debe gestionar
[keyfile]
unmanaged-devices=interface-name:wlan1;interface-name:wlan1mon;interface-name:wlan0mon
EOF
    systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager 2>/dev/null || true
    echo "[+] NetworkManager configurado"
else
    echo "[*] NetworkManager no activo, nada que configurar"
fi

echo "[+] Configuración de hardware completa."
echo "    NOTA: algunos cambios requieren reinicio para aplicarse."
