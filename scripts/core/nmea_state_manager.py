"""
PHASMIDA Core
==============================

NMEA State Manager

Responsabilidades:
    - Recibir mensajes PHASMIDA Secure NMEA.
    - Interpretar el estado de navegación.
    - Mantener un estado común para las visualizaciones.
    - Reenviar el mensaje original al IDS.
"""

import json
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.nmea_state import update_state


class NMEAStateManager:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 10120,
        ids_host: str = "phasmida_ids",
        ids_port: int = 10110
    ) -> None:
        self.host = host
        self.port = port
        self.ids_host = ids_host
        self.ids_port = ids_port

        self.receive_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )
        self.receive_socket.bind((self.host, self.port))

        self.forward_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        print("=" * 60)
        print("PHASMIDA Core")
        print("NMEA State Manager iniciado")
        print(f"Escuchando en {self.host}:{self.port}")
        print(f"Reenvío IDS: {self.ids_host}:{self.ids_port}")
        print("=" * 60)

    @staticmethod
    def nmea_coord_to_decimal(
        value: str,
        hemisphere: str
    ) -> float:
        if not value:
            raise ValueError("Coordenada NMEA vacía")

        decimal_position = value.find(".")

        if decimal_position < 0:
            raise ValueError(
                f"Coordenada NMEA inválida: {value}"
            )

        degree_digits = decimal_position - 2
        degrees = float(value[:degree_digits])
        minutes = float(value[degree_digits:])

        decimal_value = degrees + minutes / 60.0

        if hemisphere in {"S", "W"}:
            decimal_value *= -1

        return decimal_value

    def parse_nmea_state(self, sentence: str) -> dict:
        body = sentence[1:].split("*", 1)[0]
        fields = body.split(",")

        header = fields[0]
        sentence_type = header[2:]

        updates: dict = {}

        try:
            if sentence_type == "RMC":
                updates["position"] = {
                    "latitude": self.nmea_coord_to_decimal(
                        fields[3],
                        fields[4]
                    ),
                    "longitude": self.nmea_coord_to_decimal(
                        fields[5],
                        fields[6]
                    )
                }

                updates["navigation"] = {
                    "speed_knots": (
                        float(fields[7])
                        if fields[7]
                        else None
                    ),
                    "course_deg": (
                        float(fields[8])
                        if fields[8]
                        else None
                    )
                }

            elif sentence_type == "GGA":
                updates["position"] = {
                    "latitude": self.nmea_coord_to_decimal(
                        fields[2],
                        fields[3]
                    ),
                    "longitude": self.nmea_coord_to_decimal(
                        fields[4],
                        fields[5]
                    ),
                    "altitude_m": (
                        float(fields[9])
                        if fields[9]
                        else None
                    )
                }

            elif sentence_type == "VTG":
                updates["navigation"] = {
                    "course_deg": (
                        float(fields[1])
                        if fields[1]
                        else None
                    ),
                    "speed_knots": (
                        float(fields[5])
                        if fields[5]
                        else None
                    )
                }

            elif sentence_type in {"HDT", "HDG", "HDM"}:
                updates["navigation"] = {
                    "heading_deg": (
                        float(fields[1])
                        if fields[1]
                        else None
                    )
                }

            elif sentence_type in {"DBT", "DPT"}:
                if sentence_type == "DBT":
                    depth_m = (
                        float(fields[3])
                        if fields[3]
                        else None
                    )
                else:
                    depth_m = (
                        float(fields[1])
                        if fields[1]
                        else None
                    )

                updates["depth"] = {
                    "meters": depth_m
                }

            elif sentence_type == "RPM":
                updates["engine"] = {
                    "rpm": (
                        float(fields[3])
                        if len(fields) > 3 and fields[3]
                        else None
                    )
                }

        except (ValueError, IndexError):
            return {}

        return updates

    def process_message(
        self,
        raw_data: bytes,
        source_ip: str
    ) -> None:
        try:
            decoded = raw_data.decode(
                "utf-8",
                errors="ignore"
            ).strip()

            message = json.loads(decoded)

            if not isinstance(message, dict):
                raise ValueError(
                    "El mensaje recibido no es un objeto JSON"
                )

            sentence = str(message["nmea"]).strip()

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError
        ) as error:
            print(
                f"[CORE ERROR] Mensaje inválido desde "
                f"{source_ip}: {error}",
                flush=True
            )
            return

        header = sentence[1:].split("*", 1)[0].split(",", 1)[0]
        talker_id = header[:2] if len(header) >= 2 else None
        sentence_type = header[2:] if len(header) >= 5 else None

        updates = self.parse_nmea_state(sentence)

        update_state(
            updates,
            source_ip=source_ip,
            sentence=sentence,
            sentence_type=sentence_type,
            talker_id=talker_id,
            suspicious=False,
            alerts=[]
        )

        self.forward_socket.sendto(
            raw_data,
            (self.ids_host, self.ids_port)
        )

        print(
            f"[CORE RX] {source_ip} | "
            f"Talker={talker_id or 'UNKNOWN'} | "
            f"Type={sentence_type or 'UNKNOWN'} | "
            f"Forwarded to IDS",
            flush=True
        )

    def run(self) -> None:
        try:
            while True:
                data, address = self.receive_socket.recvfrom(4096)

                self.process_message(
                    data,
                    address[0]
                )

        except KeyboardInterrupt:
            print("\nPHASMIDA Core detenido.", flush=True)

        finally:
            self.receive_socket.close()
            self.forward_socket.close()
