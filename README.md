# WiFang

> Proyecto de auditoría WiFi de código abierto: dispositivo autónomo de pentesting basado en Raspberry Pi Zero 2 W con interfaz OLED y control por 3 botones físicos.  
> Diseñado para auditoría de redes propias o con autorización explícita, sin necesidad de teclado, monitor ni conexión externa.

<p align="center">
  <img src="docs/images/wifang_banner.png" width="600">
</p>

---

## Arquitectura del proyecto

WiFang captura handshakes WPA/WPA2 y ataca routers con WPS activo usando una antena USB en modo monitor. Toda la interacción se hace mediante una pantalla OLED 128×64 y tres botones físicos, lo que permite operarlo como un dispositivo autónomo tipo "caja negra".

**Componentes del sistema:**
- **Raspberry Pi Zero 2 W** → cerebro del dispositivo, ejecuta toda la lógica.
- **Antena USB WiFi (mt7601u)** → modo monitor e inyección de paquetes.
- **Pantalla OLED SSD1306 128×64 (I2C)** → interfaz de usuario.
- **3 botones físicos** → navegación (arriba / abajo / seleccionar).
- **Servicio systemd** → arranque automático al encender, sin login.

<p align="center">
  <img src="docs/images/wifang_hardware.jpg" width="400">
</p>

---

## Diagrama de conexión

Esquema de conexión entre la Raspberry Pi Zero 2 W, la pantalla OLED y los 3 botones:

| Componente | Pin Raspberry Pi (BCM) |
|------------|------------------------|
| OLED VCC   | 3.3V (pin 1)           |
| OLED GND   | GND (pin 6)            |
| OLED SDA   | GPIO2 / SDA (pin 3)    |
| OLED SCL   | GPIO3 / SCL (pin 5)    |
| Botón UP   | GPIO17                 |
| Botón DOWN | GPIO27                 |
| Botón SELECT | GPIO22               |
| Botón GND (común) | GND (pin 9)     |

<p align="center">
  <img src="docs/images/wifang_wiring.png" width="600">
</p>

---

## Funcionalidades

WiFang ofrece un menú principal con las siguientes opciones:

| Módulo | Descripción |
|--------|-------------|
| **Modo Monitor** | Detecta antenas WiFi disponibles y las activa/desactiva en modo monitor. |
| **Handshake** | Escanea redes con clientes activos, lanza deauth y captura handshakes WPA/WPA2 con wifite. |
| **WPS Attack** | Escanea redes con WPS activo (wash) y ataca el PIN con wifite (reaver/bully). |
| **Guardados** | Lista las redes crackeadas con su contraseña (lectura de `cracked.json`). |
| **Energía** | Apagado y reinicio del dispositivo con confirmación por botones. |

---

## Capturas del dispositivo

<p align="center">
  <img src="docs/images/wifang_logo.png" width="300">
  <img src="docs/images/wifang_menu.png" width="300">
</p>

<p align="center">
  <em>Logo de arranque y menú principal en la OLED</em>
</p>

---

## Instalación

### Requisitos

- Raspberry Pi Zero 2 W (o cualquier Pi con puerto USB).
- Raspberry Pi OS Bookworm (probado) o Bullseye.
- Antena USB WiFi compatible con modo monitor (probado con chipset **mt7601u**).
- Pantalla OLED SSD1306 128×64 con interfaz I2C.
- 3 botones pulsadores (tipo táctil o mecánico).

### Instalación en 3 pasos

1. Clona el repositorio en la Raspberry Pi:
   ```bash
   git clone https://github.com/tu-usuario/WiFang.git
   cd WiFang
