#!/bin/bash
# Funciones comunes para los scripts del instalador

# ¿Existe el comando?
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ¿Paquete apt instalado?
apt_installed() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

# Backup de un archivo (idempotente)
backup_file() {
    local file="$1"
    if [[ -f "$file" ]] && [[ ! -f "${file}.wifang.bak" ]]; then
        cp "$file" "${file}.wifang.bak"
    fi
}
