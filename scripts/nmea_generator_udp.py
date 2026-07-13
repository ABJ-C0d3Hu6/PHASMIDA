import hashlib
import hmac
import json
import math
import os
import random
import socket
import time
from datetime import datetime, timezone


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

CORE_HOST = os.getenv("PHASMIDA_CORE_HOST", "phasmida_core")
CORE_PORT = int(os.getenv("PHASMIDA_CORE_PORT", "10120"))

SEND_INTERVAL = 1.0
SECRET_KEY = b"PHASMIDA_SECRET_2026"

# Estado inicial del buque: costa de Alicante
CURRENT_LAT = 38.335
CURRENT_LON = -0.430
CURRENT_COURSE = 75.0
CURRENT_SPEED = 10.5


# ==========================================================
# FUNCIONES NMEA
# ==========================================================

def checksum(body: str) -> str:
    value = 0

    for character in body:
        value ^= ord(character)

    return f"{value:02X}"


def build(body: str) -> str:
    return f"${body}*{checksum(body)}"


def decimal_to_nmea_lat(latitude: float) -> tuple[str, str]:
    hemisphere = "N" if latitude >= 0 else "S"
    latitude = abs(latitude)

    degrees = int(latitude)
    minutes = (latitude - degrees) * 60.0

    return f"{degrees:02d}{minutes:06.3f}", hemisphere


def decimal_to_nmea_lon(longitude: float) -> tuple[str, str]:
    hemisphere = "E" if longitude >= 0 else "W"
    longitude = abs(longitude)

    degrees = int(longitude)
    minutes = (longitude - degrees) * 60.0

    return f"{degrees:03d}{minutes:06.3f}", hemisphere


def advance_position(
    latitude: float,
    longitude: float,
    speed_knots: float,
    course_deg: float,
    interval_seconds: float
) -> tuple[float, float]:
    """
    Calcula una nueva posición aproximada a partir de la
    velocidad, el rumbo y el intervalo temporal.
    """

    distance_nm = speed_knots * interval_seconds / 3600.0
    course_rad = math.radians(course_deg)
    latitude_rad = math.radians(latitude)

    north_displacement_nm = distance_nm * math.cos(course_rad)
    east_displacement_nm = distance_nm * math.sin(course_rad)

    delta_lat = north_displacement_nm / 60.0

    longitude_scale = max(
        60.0 * math.cos(latitude_rad),
        0.01
    )

    delta_lon = east_displacement_nm / longitude_scale

    new_latitude = latitude + delta_lat
    new_longitude = longitude + delta_lon

    return new_latitude, new_longitude


def update_navigation_state() -> None:
    """
    Modifica ligeramente velocidad y rumbo y actualiza
    la posición del buque.
    """
    global CURRENT_LAT
    global CURRENT_LON
    global CURRENT_COURSE
    global CURRENT_SPEED

    CURRENT_COURSE += random.uniform(-1.0, 1.0)
    CURRENT_COURSE %= 360.0

    CURRENT_SPEED += random.uniform(-0.2, 0.2)
    CURRENT_SPEED = max(
        6.0,
        min(CURRENT_SPEED, 14.0)
    )

    CURRENT_LAT, CURRENT_LON = advance_position(
        CURRENT_LAT,
        CURRENT_LON,
        CURRENT_SPEED,
        CURRENT_COURSE,
        SEND_INTERVAL
    )


def generate_rmc() -> str:
    now = datetime.now(timezone.utc)

    update_navigation_state()

    lat_value, lat_hemisphere = decimal_to_nmea_lat(
        CURRENT_LAT
    )
    lon_value, lon_hemisphere = decimal_to_nmea_lon(
        CURRENT_LON
    )

    body = (
        f"GPRMC,{now.strftime('%H%M%S')},A,"
        f"{lat_value},{lat_hemisphere},"
        f"{lon_value},{lon_hemisphere},"
        f"{CURRENT_SPEED:.1f},"
        f"{CURRENT_COURSE:.1f},"
        f"{now.strftime('%d%m%y')},,,A"
    )

    return build(body)


def generate_gga() -> str:
    now = datetime.now(timezone.utc)

    lat_value, lat_hemisphere = decimal_to_nmea_lat(
        CURRENT_LAT
    )
    lon_value, lon_hemisphere = decimal_to_nmea_lon(
        CURRENT_LON
    )

    satellites = random.randint(7, 12)
    altitude_m = 15.0

    body = (
        f"GPGGA,{now.strftime('%H%M%S')},"
        f"{lat_value},{lat_hemisphere},"
        f"{lon_value},{lon_hemisphere},"
        f"1,{satellites},1.0,"
        f"{altitude_m:.1f},M,0.0,M,,"
    )

    return build(body)


# ==========================================================
# MENSAJE SEGURO PHASMIDA
# ==========================================================

def calculate_hmac(
    nmea_sentence: str,
    timestamp: str,
    sensor: str
) -> str:
    payload = f"{nmea_sentence}|{timestamp}|{sensor}"

    return hmac.new(
        SECRET_KEY,
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def build_secure_message(nmea_sentence: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    sensor = "gps_node"

    signature = calculate_hmac(
        nmea_sentence,
        timestamp,
        sensor
    )

    return {
        "sensor": sensor,
        "timestamp": timestamp,
        "nmea": nmea_sentence,
        "hmac": signature
    }


# ==========================================================
# EJECUCIÓN
# ==========================================================

def main() -> None:
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    print(
        f"GPS node enviando NMEA seguro a "
        f"PHASMIDA Core ({CORE_HOST}:{CORE_PORT})",
        flush=True
    )

    print(
        f"Posición inicial: "
        f"{CURRENT_LAT:.6f}, {CURRENT_LON:.6f}",
        flush=True
    )

    try:
        while True:
            # Se envía RMC en cada ciclo para mantener
            # posición, velocidad y rumbo actualizados.
            rmc_sentence = generate_rmc()
            rmc_message = build_secure_message(rmc_sentence)

            sock.sendto(
                json.dumps(rmc_message).encode("utf-8"),
                (CORE_HOST, CORE_PORT)
            )

            print(
                f"[TX CORE] {rmc_sentence}",
                flush=True
            )

            # GGA se envía después para aportar información
            # adicional de posicionamiento y altitud.
            gga_sentence = generate_gga()
            gga_message = build_secure_message(gga_sentence)

            sock.sendto(
                json.dumps(gga_message).encode("utf-8"),
                (CORE_HOST, CORE_PORT)
            )

            print(
                f"[TX CORE] {gga_sentence}",
                flush=True
            )

            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print(
            "\nGPS node detenido.",
            flush=True
        )

    finally:
        sock.close()


if __name__ == "__main__":
    main()