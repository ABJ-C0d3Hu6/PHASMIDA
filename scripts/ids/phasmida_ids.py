import os
import csv
import socket
import time
import json
import hmac
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timezone

HOST = "0.0.0.0"
PORT = 10110
MAX_MESSAGES_PER_SECOND = 10
EVENTS_DIR = "events"
CSV_LOG = os.path.join(EVENTS_DIR, "phasmida_events.csv")
JSONL_LOG = os.path.join(EVENTS_DIR, "phasmida_events.jsonl")
SECRET_KEY = b"PHASMIDA_SECRET_2026"

# ==========================================================
# CONFIGURACIÓN DEL IDS
# ==========================================================

# Sentencias NMEA permitidas
ALLOWED_SENTENCES = {
    "GGA",
    "RMC",
    "VTG",
    "HDG",
    "HDT",
    "HDM",
    "DBT",
    "DPT",
    "RPM",
    "VDM",
    "VDO"
}

# Talker IDs permitidos
ALLOWED_TALKERS = {
    "GP",   # GPS
    "GN",   # GNSS
    "HC",   # Compás
    "SD",   # Ecosonda
    "II",   # Instrumentación integrada
    "AI"    # AIS
}

AUTHORIZED_SOURCES = {
    "10.50.10.10": "gps_node"
}

MAX_MESSAGES_PER_SECOND = 10
MAX_MESSAGE_AGE_SECONDS = 10


def nmea_checksum(body: str) -> str:
    value = 0
    for char in body:
        value ^= ord(char)
    return f"{value:02X}"


def validate_checksum(sentence: str):
    sentence = sentence.strip()

    if not sentence.startswith(("$", "!")) or "*" not in sentence:
        return False, "Formato NMEA inválido"


    try:
        body, received = sentence[1:].split("*", 1)
        received = received[:2].upper()
        calculated = nmea_checksum(body)

        if calculated != received:
            return False, f"Checksum inválido recibido={received}, calculado={calculated}"

        return True, "OK"

    except Exception as e:
        return False, f"Error validando checksum: {e}"


def classify_sentence(sentence: str):
    try:
        body = sentence[1:].split("*")[0]
        header = body.split(",")[0]
        sentence_type = header[2:]

        if sentence_type in ["RMC", "GGA"]:
            return sentence_type, "GNSS"
        elif sentence_type in ["HDG", "HDT", "HDM"]:
            return sentence_type, "RUMBO"
        elif sentence_type in ["DBT", "DPT"]:
            return sentence_type, "SONDA"
        elif sentence_type in ["VDM", "VDO"]:
            return sentence_type, "AIS"
        else:
            return sentence_type, "DESCONOCIDO"

    except Exception:
        return "UNKNOWN", "DESCONOCIDO"

def validate_nmea_header(sentence: str):
    """
    Valida el Talker ID y el tipo de sentencia NMEA frente
    a las listas blancas configuradas para PHASMIDA.
    """
    try:
        sentence = sentence.strip()

        if not sentence.startswith(("$", "!")):
            return False, None, None, "Cabecera NMEA inválida"


        body = sentence[1:].split("*", 1)[0]
        header = body.split(",", 1)[0]

        if len(header) < 5:
            return False, None, None, f"Cabecera NMEA incompleta: {header}"

        talker = header[:2]
        sentence_type = header[2:]

        errors = []

        if talker not in ALLOWED_TALKERS:
            errors.append(f"Talker ID no autorizado: {talker}")

        if sentence_type not in ALLOWED_SENTENCES:
            errors.append(f"Tipo de sentencia no permitido: {sentence_type}")

        if errors:
            return False, talker, sentence_type, "; ".join(errors)

        return True, talker, sentence_type, "OK"

    except Exception as e:
        return False, None, None, f"Error validando cabecera NMEA: {e}"

def calculate_hmac(nmea_sentence, timestamp, sensor):
    payload = f"{nmea_sentence}|{timestamp}|{sensor}"
    return hmac.new(
        SECRET_KEY,
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def validate_hmac(message):
    required_fields = ["sensor", "timestamp", "nmea", "hmac"]

    for field in required_fields:
        if field not in message:
            return False, f"Campo ausente en mensaje seguro: {field}"

    expected = calculate_hmac(
        message["nmea"],
        message["timestamp"],
        message["sensor"]
    )

    received = message["hmac"]

    if not hmac.compare_digest(expected, received):
        return False, "HMAC inválido. Posible manipulación o suplantación."

    return True, "OK"


def validate_timestamp(timestamp):
    try:
        msg_time = datetime.fromisoformat(timestamp)
        now = datetime.now(timezone.utc)

        age = abs((now - msg_time).total_seconds())

        if age > MAX_MESSAGE_AGE_SECONDS:
            return False, f"Timestamp fuera de ventana temporal: {age:.1f} s"

        return True, "OK"

    except Exception as e:
        return False, f"Timestamp inválido: {e}"


def ensure_event_files():
    os.makedirs(EVENTS_DIR, exist_ok=True)

    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "alert_type",
                    "severity",
                    "source_ip",
                    "message",
                    "raw_sentence"
                ]
            )
            writer.writeheader()


def write_event(event):
    ensure_event_files()

    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "alert_type",
                "severity",
                "source_ip",
                "message",
                "raw_sentence"
            ]
        )
        writer.writerow(event)

    with open(JSONL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def create_alert(alert_type, severity, source_ip, message, raw_sentence):
    timestamp = datetime.now(timezone.utc).isoformat()

    event = {
        "timestamp": timestamp,
        "alert_type": alert_type,
        "severity": severity,
        "source_ip": source_ip,
        "message": message,
        "raw_sentence": raw_sentence
    }

    write_event(event)

    print("\n" + "=" * 70, flush=True)
    print(f"[ALERTA PHASMIDA] {timestamp}", flush=True)
    print(f"Tipo:      {alert_type}", flush=True)
    print(f"Severidad: {severity}", flush=True)
    print(f"Origen:    {source_ip}", flush=True)
    print(f"Mensaje:   {message}", flush=True)
    print(f"Trama:     {raw_sentence}", flush=True)
    print("=" * 70 + "\n", flush=True)

def parse_secure_message(raw_data):
    try:
        decoded = raw_data.decode("utf-8", errors="ignore").strip()
        message = json.loads(decoded)

        if not isinstance(message, dict):
            return None, decoded, "El mensaje recibido no es un objeto JSON"

        return message, decoded, None

    except Exception as e:
        decoded = raw_data.decode("utf-8", errors="ignore").strip()
        return None, decoded, f"Mensaje no compatible con PHASMIDA Secure NMEA: {e}"


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))

    print(f"PHASMIDA IDS escuchando en UDP {HOST}:{PORT}", flush=True)
    print(f"Fuentes autorizadas: {AUTHORIZED_SOURCES}", flush=True)
    print("Modo seguro: HMAC-SHA256 activado", flush=True)

    packet_times = defaultdict(deque)

    while True:
        data, addr = sock.recvfrom(4096)

        source_ip = addr[0]
        source_port = addr[1]
        now = time.time()

        message, raw_payload, parse_error = parse_secure_message(data)

        if parse_error:
            create_alert(
                "INVALID_SECURE_FORMAT",
                "HIGH",
                source_ip,
                parse_error,
                raw_payload
            )
            continue

        # Evita errores si falta algún campo obligatorio.
        required_fields = {"sensor", "timestamp", "nmea", "hmac"}

        if not required_fields.issubset(message):
            missing_fields = required_fields - set(message)

            create_alert(
                "MISSING_SECURE_FIELDS",
                "HIGH",
                source_ip,
                f"Campos obligatorios ausentes: {sorted(missing_fields)}",
                raw_payload
            )
            continue

        hmac_valid, hmac_msg = validate_hmac(message)
        timestamp_valid, timestamp_msg = validate_timestamp(
            message["timestamp"]
        )

        sentence = message["nmea"].strip()

        valid_checksum, checksum_msg = validate_checksum(sentence)

        (
            header_valid,
            talker_id,
            sentence_type,
            header_msg
        ) = validate_nmea_header(sentence)

        classified_type, category = classify_sentence(sentence)

        print(
            f"[RX] {source_ip}:{source_port} | "
            f"Talker={talker_id or 'UNKNOWN'} | "
            f"{classified_type}/{category} | "
            f"Header={'OK' if header_valid else 'FAIL'} | "
            f"HMAC={'OK' if hmac_valid else 'FAIL'} | "
            f"Checksum={'OK' if valid_checksum else 'FAIL'} | "
            f"{sentence}",
            flush=True
        )

        if source_ip not in AUTHORIZED_SOURCES:
            create_alert(
                "UNAUTHORIZED_SOURCE",
                "HIGH",
                source_ip,
                "Trama recibida desde una fuente no autorizada",
                sentence
            )

        if not header_valid:
            create_alert(
                "INVALID_NMEA_HEADER",
                "HIGH",
                source_ip,
                header_msg,
                sentence
            )

        if not hmac_valid:
            create_alert(
                "INVALID_HMAC",
                "CRITICAL",
                source_ip,
                hmac_msg,
                sentence
            )

        if not timestamp_valid:
            create_alert(
                "INVALID_TIMESTAMP",
                "HIGH",
                source_ip,
                timestamp_msg,
                sentence
            )

        if not valid_checksum:
            create_alert(
                "INVALID_CHECKSUM",
                "MEDIUM",
                source_ip,
                checksum_msg,
                sentence
            )

        times = packet_times[source_ip]
        times.append(now)

        while times and now - times[0] > 1:
            times.popleft()

        if len(times) > MAX_MESSAGES_PER_SECOND:
            create_alert(
                "NMEA_FLOOD",
                "HIGH",
                source_ip,
                (
                    "Exceso de tráfico NMEA detectado: "
                    f"{len(times)} tramas/s"
                ),
                sentence
            )


if __name__ == "__main__":
    main()
