#!/bin/sh

echo "[PHASMIDA] Aplicando reglas IPTables..."

iptables -F
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Permitir loopback
iptables -A INPUT -i lo -j ACCEPT

# Permitir tráfico NMEA legítimo desde gps_node
iptables -A INPUT -p udp -s 172.25.0.10 --dport 10110 -j ACCEPT

# Permitir ping para pruebas
iptables -A INPUT -p icmp -j ACCEPT

echo "[PHASMIDA] Reglas activas:"
iptables -L -n -v

echo "[PHASMIDA] Lanzando IDS..."
python phasmida_ids.py
