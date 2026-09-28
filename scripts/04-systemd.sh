#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

REAL_USER="$1"
PROJECT_DIR="$2"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
SERVICE_NAME="wifang"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# ------------------------------------------------------------ #
#  Verificar que el venv existe                                #
# ------------------------------------------------------------ #
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "[-] No existe $VENV_PYTHON. Ejecuta primero 02-python-env.sh"
    exit 1
fi

# ------------------------------------------------------------ #
#  Generar archivo de servicio                                 #
# ------------------------------------------------------------ #
echo "[*] Generando $SERVICE_FILE"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=WiFang - WiFi Pentest Toolkit
After=network.target multi-user.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment="PYTHONUNBUFFERED=1"
Environment="HOME=$PROJECT_DIR"
ExecStart=$VENV_PYTHON $PROJECT_DIR/main.py
Restart=on-failure
RestartSec=5

# Logs
StandardOutput=journal
StandardError=journal

# Seguridad (comenta si algo se rompe)
# ProtectSystem=full
# PrivateTmp=false
# NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "$SERVICE_FILE"

# ------------------------------------------------------------ #
#  Recargar systemd y habilitar                                #
# ------------------------------------------------------------ #
echo "[*] Recargando systemd..."
systemctl daemon-reload

echo "[*] Habilitando servicio al arranque..."
systemctl enable "$SERVICE_NAME.service"

# No lo arrancamos aquí — el instalador solo lo deja listo.
# El usuario decide si reiniciar o arrancarlo manualmente.
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
    echo "[*] Servicio ya en ejecución. Reiniciando..."
    systemctl restart "$SERVICE_NAME.service"
fi

echo "[+] Servicio systemd instalado y habilitado."
echo "    Arrancar ahora:  sudo systemctl start $SERVICE_NAME"
echo "    Ver estado:      sudo systemctl status $SERVICE_NAME"
echo "    Ver logs:        sudo journalctl -u $SERVICE_NAME -f"
