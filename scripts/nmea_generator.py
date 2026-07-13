import random
import time
import socket
from datetime import datetime

UDP_IP = "127.0.0.1"
UDP_PORT = 10110
SEND_INTERVAL = 1.0


def nmea_checksum(sentence_body: str) -> str:
    checksum = 0
    for char in sentence_body:
        checksum ^= ord(char)
    return f"{checksum:02X}"


def build_nmea_sentence(body: str) -> str:
    return f"${body}*{nmea_checksum(body)}"


def generate_gprmc() -> str:
    now = datetime.utcnow()
    time_utc = now.strftime("%H%M%S")
    date_utc = now.strftime("%d%m%y")

    latitude = "3800.000"
    longitude = "00030.000"
    speed_knots = round(random.uniform(5.0, 15.0), 1)
    course = round(random.uniform(80.0, 100.0), 1)

    body = (
        f"GPRMC,{time_utc},A,"
        f"{latitude},N,"
        f"{longitude},W,"
        f"{speed_knots},{course},"
        f"{date_utc},,,A"
    )
    return build_nmea_sentence(body)


def generate_gpgga() -> str:
    now = datetime.utcnow()
    time_utc = now.strftime("%H%M%S")

    latitude = "3800.000"
    longitude = "00030.000"
    fix_quality = 1
    num_satellites = random.randint(6, 12)
    hdop = round(random.uniform(0.7, 1.8), 1)
    altitude = round(random.uniform(5.0, 30.0), 1)

    body = (
        f"GPGGA,{time_utc},"
        f"{latitude},N,"
        f"{longitude},W,"
        f"{fix_quality},{num_satellites},"
        f"{hdop},{altitude},M,0.0,M,,"
    )
    return build_nmea_sentence(body)


def generate_hchdg() -> str:
    heading = round(random.uniform(80.0, 100.0), 1)
    body = f"HCHDG,{heading},,,,"
    return build_nmea_sentence(body)


def generate_sddbt() -> str:
    depth_m = round(random.uniform(20.0, 80.0), 1)
    depth_ft = round(depth_m * 3.28084, 1)
    depth_fathoms = round(depth_m * 0.546807, 1)

    body = f"SDDBT,{depth_ft},f,{depth_m},M,{depth_fathoms},F"
    return build_nmea_sentence(body)


def generate_nmea_sentence() -> str:
    generators = [
        generate_gprmc,
        generate_gpgga,
        generate_hchdg,
        generate_sddbt,
    ]
    return random.choice(generators)()


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"Enviando tramas NMEA por UDP a {UDP_IP}:{UDP_PORT}")
    print("Pulsa Ctrl+C para detener.\n")

    try:
        while True:
            sentence = generate_nmea_sentence()
            sock.sendto(sentence.encode("ascii"), (UDP_IP, UDP_PORT))
            print(sentence)
            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print("\nGenerador detenido.")

    finally:
        sock.close()


if __name__ == "__main__":
    main()