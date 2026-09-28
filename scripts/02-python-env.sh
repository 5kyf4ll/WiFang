#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

REAL_USER="$1"
PROJECT_DIR="$2"
VENV_DIR="$PROJECT_DIR/venv"

# ------------------------------------------------------------ #
#  Crear venv (o recrearlo si no existe)                       #
# ------------------------------------------------------------ #
if [[ ! -d "$VENV_DIR" ]]; then
    echo "[*] Creando entorno virtual en $VENV_DIR"
    sudo -u "$REAL_USER" python3 -m venv "$VENV_DIR"
else
    echo "[*] Reutilizando venv existente en $VENV_DIR"
fi

# ------------------------------------------------------------ #
#  Actualizar pip                                              #
# ------------------------------------------------------------ #
echo "[*] Actualizando pip y wheel..."
sudo -u "$REAL_USER" "$VENV_DIR/bin/pip" install --upgrade --quiet pip wheel setuptools

# ------------------------------------------------------------ #
#  Instalar requirements                                       #
# ------------------------------------------------------------ #
if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
    echo "[!] No existe requirements.txt en $PROJECT_DIR"
    exit 1
fi

echo "[*] Instalando dependencias Python desde requirements.txt..."
sudo -u "$REAL_USER" "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"

# ------------------------------------------------------------ #
#  Verificar imports                                           #
# ------------------------------------------------------------ #
echo "[*] Verificando imports..."
sudo -u "$REAL_USER" "$VENV_DIR/bin/python3" - <<'PYEOF'
import sys
try:
    import board, busio
    import adafruit_ssd1306
    import PIL
    import RPi.GPIO
    print("[+] Todos los imports OK")
except Exception as e:
    print(f"[-] Error importando: {e}")
    sys.exit(1)
PYEOF

# ------------------------------------------------------------ #
#  Descomprimir wordlist si está en .gz                        #
# ------------------------------------------------------------ #
WORDLIST_GZ="$PROJECT_DIR/modules/wordlist.txt.gz"
WORDLIST_TXT="$PROJECT_DIR/modules/wordlist.txt"

if [[ -f "$WORDLIST_GZ" && ! -f "$WORDLIST_TXT" ]]; then
    echo "[*] Descomprimiendo wordlist..."
    sudo -u "$REAL_USER" gunzip -k "$WORDLIST_GZ"
    echo "[+] wordlist.txt listo"
elif [[ -f "$WORDLIST_TXT" ]]; then
    echo "[*] wordlist.txt ya existe, sin cambios"
else
    echo "[!] No se encontró wordlist.txt.gz ni wordlist.txt"
    echo "    Los ataques con diccionario fallarán hasta que la añadas."
fi

# ------------------------------------------------------------ #
#  Permisos                                                    #
# ------------------------------------------------------------ #
chown -R "$REAL_USER:$REAL_USER" "$VENV_DIR"

echo "[+] Entorno virtual listo."
