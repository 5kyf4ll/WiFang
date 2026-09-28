#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

echo "[*] Actualizando índice de paquetes..."
apt-get update -qq

# ------------------------------------------------------------ #
#  Paquetes base                                               #
# ------------------------------------------------------------ #
PACKAGES_BASE=(
    python3
    python3-pip
    python3-venv
    python3-dev
    i2c-tools
    git
    unzip
    rsync
    jq
)

# ------------------------------------------------------------ #
#  Herramientas de pentesting WiFi                             #
#  (wifite necesita todas estas para funcionar de verdad)      #
# ------------------------------------------------------------ #
PACKAGES_WIFI=(
    aircrack-ng
    reaver
    bully
    wifite
    hcxtools
    hcxdumptool
    pixiewps
    macchanger
    cowpatty
    tshark
    hostapd
    wpasupplicant
    wireless-tools
    rfkill
)

# ------------------------------------------------------------ #
#  Instalación                                                 #
# ------------------------------------------------------------ #
echo "[*] Instalando paquetes base..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${PACKAGES_BASE[@]}"

echo "[*] Instalando herramientas de pentesting WiFi..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${PACKAGES_WIFI[@]}" || {
    echo "[!] Algunos paquetes WiFi fallaron. Revisando uno a uno..."
    for pkg in "${PACKAGES_WIFI[@]}"; do
        if ! apt_installed "$pkg"; then
            echo "  -> instalando $pkg"
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg" || \
                echo "  [!] no se pudo instalar $pkg (puede que no exista en este repo)"
        fi
    done
}

# ------------------------------------------------------------ #
#  Verificación                                                #
# ------------------------------------------------------------ #
echo "[*] Verificando herramientas clave:"
for tool in aircrack-ng wifite reaver wash hcxdumptool; do
    if command_exists "$tool"; then
        echo "    [+] $tool"
    else
        echo "    [-] $tool NO encontrado"
    fi
done

echo "[+] Dependencias del sistema instaladas."
