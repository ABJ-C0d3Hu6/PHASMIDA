#!/bin/sh
set -eu

echo "[PHASMIDA FIREWALL] Inicializando reglas ACL..."

# El reenvío IPv4 se activa desde docker-compose.yml.
# No debe ejecutarse sysctl aquí en Docker Desktop para macOS.

iptables -F
iptables -X
iptables -t nat -F

iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -P FORWARD DROP

iptables -A FORWARD \
    -m conntrack \
    --ctstate ESTABLISHED,RELATED \
    -j ACCEPT

# Red Team -> IDS NMEA
iptables -A FORWARD \
    -s 10.50.30.99 \
    -d 10.50.10.30 \
    -p udp \
    --dport 10110 \
    -j ACCEPT

# IDMZ -> Dashboard OT
iptables -A FORWARD \
    -s 10.50.20.10 \
    -d 10.50.10.40 \
    -p tcp \
    --dport 8501 \
    -j ACCEPT

# NAT Red Team -> OT
iptables -t nat -A POSTROUTING \
    -s 10.50.30.0/24 \
    -d 10.50.10.0/24 \
    -j MASQUERADE

# NAT IDMZ -> OT
iptables -t nat -A POSTROUTING \
    -s 10.50.20.0/24 \
    -d 10.50.10.0/24 \
    -j MASQUERADE

# NGINX en IDMZ -> Dashboard en OT
iptables -A FORWARD \
    -s 10.50.20.10 \
    -d 10.50.10.40 \
    -p tcp \
    --dport 8501 \
    -j ACCEPT

echo "[PHASMIDA FIREWALL] ACL cargada correctamente."

iptables -L FORWARD -n -v
iptables -t nat -L POSTROUTING -n -v

exec tail -f /dev/null
