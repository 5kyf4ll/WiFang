#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

REAL_USER="$1"
PROJECT_DIR="$2"
VENV_DIR="$PROJECT_DIR/venv"

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

OK="[${GREEN}OK${NC}]"
FAIL="[${RED}!!${NC}]"
WARN="[${YELLOW}??${NC}]"

echo ""
echo "=========================================="
echo "  Verificación final"
echo "=========================================="

# Python
if command_exists python3; then
    echo -e " $OK  Python: $(python3 --version)"
else
    echo -e " $FAIL  Python no encontrado"
fi

# venv
if [[ -x "$VENV_DIR/bin/python3" ]]; then
    echo -e " $OK  Venv:   $VENV_DIR"
else
    echo -e " $FAIL  Venv no encontrado"
fi

# requirements
if [[ -x "$VENV_DIR/bin/python3" ]] && \
   "$VENV_DIR/bin/python3" -c "import board, adafruit_ssd1306, PIL, RPi.GPIO" 2>/dev/null; then
    echo -e " $OK  Imports Python (board, oled, PIL, GPIO)"
else
    echo -e " $FAIL  Faltan imports Python"
fi

# Herramientas WiFi
for tool in aircrack-ng wifite wash reaver bully hcxdumptool iw; do
    if command_exists "$tool"; then
        echo -e " $OK  $tool"
    else
        echo -e " $FAIL  $tool no instalado"
    fi
done

# Sudoers
if [[ -f /etc/sudoers.d/wifang ]]; then
    echo -e " $OK  Regla sudoers instalada"
else
    echo -e " $FAIL  Regla sudoers ausente"
fi

# Servicio systemd
if [[ -f /etc/systemd/system/wifang.service ]]; then
    if systemctl is-enabled --quiet wifang.service 2>/dev/null; then
        echo -e " $OK  Servicio wifang habilitado al arranque"
    else
        echo -e " $WARN  Servicio wifang existe pero no está habilitado"
    fi
else
    echo -e " $FAIL  Servicio systemd no instalado"
fi

# I2C
if command_exists i2cdetect; then
    if i2cdetect -y 1 2>/dev/null | grep -qE "3c|3d"; then
        echo -e " $OK  OLED detectada en I2C (0x3C / 0x3D)"
    else
        echo -e " $WARN  OLED no detectada en I2C (¿conectada?)"
    fi
else
    echo -e " $WARN  i2cdetect no disponible"
fi

# Wordlist
if [[ -f "$PROJECT_DIR/modules/wordlist.txt" ]]; then
    lines=$(wc -l < "$PROJECT_DIR/modules/wordlist.txt")
    echo -e " $OK  wordlist.txt ($lines líneas)"
elif [[ -f "$PROJECT_DIR/modules/wordlist.txt.gz" ]]; then
    echo -e " $WARN  wordlist.txt.gz sin descomprimir"
else
    echo -e " $FAIL  wordlist no encontrada"
fi

# Logo
if [[ -f "$PROJECT_DIR/gui/assets/logo.png" ]]; then
    echo -e " $OK  Logo presente"
else
    echo -e " $WARN  Logo ausente (se usará texto de fallback)"
fi

# Antenas WiFi
IFACES=$(iw dev 2>/dev/null | awk '/Interface/ {print $2}' | tr '\n' ' ')
if [[ -n "$IFACES" ]]; then
    echo -e " $OK  Interfaces WiFi: $IFACES"
else
    echo -e " $WARN  No se detectaron interfaces WiFi"
fi

echo "=========================================="
echo ""
