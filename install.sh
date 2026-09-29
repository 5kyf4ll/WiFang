#!/bin/bash
# ============================================================
#  WiFang Installer
#  Instala WiFang en una Raspberry Pi (Bookworm / Bullseye)
# ============================================================
set -euo pipefail

# ------------------------------------------------------------ #
#  Detección de entorno                                        #
# ------------------------------------------------------------ #
if [[ $EUID -ne 0 ]]; then
    echo "[!] Este instalador necesita sudo."
    echo "    Ejecuta: sudo bash install.sh"
    exit 1
fi

# Usuario real (no root) y su home
REAL_USER="${SUDO_USER:-$USER}"
if [[ "$REAL_USER" == "root" ]]; then
    echo "[!] No ejecutes el instalador como root directo."
    echo "    Usa: sudo bash install.sh (desde tu usuario normal)"
    exit 1
fi
REAL_HOME=$(eval echo "~$REAL_USER")
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$PROJECT_DIR/scripts"

# ------------------------------------------------------------ #
#  Colores                                                    #
# ------------------------------------------------------------ #
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
NC="\033[0m"

log()  { echo -e "${BLUE}[*]${NC} $*"; }
ok()   { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[-]${NC} $*"; }

# ------------------------------------------------------------ #
#  Banner                                                     #
# ------------------------------------------------------------ #
clear
cat <<'EOF'
   ___       _______ __
  / _ \___  / __/ _ `/ /  ___ ____
 / // / _ \/ _// __/ /___/ _ `/ _ \
/____/_//_/_/  \__/_/    \_,_/ .__/
                            /_/
EOF
echo ""
echo "  WiFang Installer"
echo "  WiFi Pentest Toolkit"
echo ""
echo "  Usuario:        $REAL_USER"
echo "  Home:           $REAL_HOME"
echo "  Proyecto:       $PROJECT_DIR"
echo ""

read -p "¿Continuar con la instalación? [s/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
    warn "Instalación cancelada por el usuario."
    exit 0
fi

# ------------------------------------------------------------ #
#  Cargar helpers                                             #
# ------------------------------------------------------------ #
source "$SCRIPTS_DIR/helpers.sh"

# ------------------------------------------------------------ #
#  Ejecutar cada paso                                         #
# ------------------------------------------------------------ #
log "Paso 1/6: Dependencias del sistema"
bash "$SCRIPTS_DIR/01-system-deps.sh"

log "Paso 2/6: Entorno virtual Python"
bash "$SCRIPTS_DIR/02-python-env.sh" "$REAL_USER" "$PROJECT_DIR"

log "Paso 3/6: Reglas sudoers"
bash "$SCRIPTS_DIR/03-sudoers.sh" "$REAL_USER"

log "Paso 4/6: Servicio systemd"
bash "$SCRIPTS_DIR/04-systemd.sh" "$REAL_USER" "$PROJECT_DIR"

log "Paso 5/6: Configuración de hardware"
bash "$SCRIPTS_DIR/05-hardware.sh" "$REAL_USER"

log "Paso 6/6: Verificación"
bash "$SCRIPTS_DIR/06-verify.sh" "$REAL_USER" "$PROJECT_DIR" || true

# ------------------------------------------------------------ #
#  Fin                                                        #
# ------------------------------------------------------------ #
echo ""
ok "=========================================="
ok "  WiFang instalado correctamente"
ok "=========================================="
echo ""
echo "  El servicio arrancará automáticamente al reiniciar."
echo ""
echo "  Comandos útiles:"
echo "    sudo systemctl start wifang       # arrancar ahora"
echo "    sudo systemctl stop wifang        # detener"
echo "    sudo systemctl status wifang      # ver estado"
echo "    sudo journalctl -u wifang -f      # ver logs en vivo"
echo ""
echo "  Para desinstalar:"
echo "    sudo bash uninstall.sh"
echo ""

# ------------------------------------------------------------ #
#  Preguntar si reiniciar ahora                               #
# ------------------------------------------------------------ #
echo ""
read -p "¿Reiniciar ahora para aplicar los cambios? [s/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[SsYy]$ ]]; then
    echo ""
    echo "[*] Reiniciando en 3 segundos..."
    echo "    (Ctrl+C para cancelar)"
    sleep 3
    systemctl reboot
else
    echo ""
    echo "[*] No se reinició."
    echo "    Puedes hacerlo manualmente cuando quieras con: sudo reboot"
fi