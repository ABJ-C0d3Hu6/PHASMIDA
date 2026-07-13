#!/bin/sh
set -eu

echo "[PHASMIDA NGINX] Configurando ruta hacia la zona OT..."

# El tráfico dirigido a la red OT debe pasar por el firewall de la IDMZ.
ip route replace 10.50.10.0/24 via 10.50.20.254

echo "[PHASMIDA NGINX] Tabla de rutas:"
ip route

echo "[PHASMIDA NGINX] Iniciando reverse proxy..."

exec nginx -g "daemon off;"
